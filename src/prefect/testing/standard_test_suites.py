import sys
import time
from abc import ABC, abstractmethod
from uuid import uuid4

import anyio
import cloudpickle
import pytest

from prefect import flow, task
from prefect.futures import PrefectFuture
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType
from prefect.task_runners import BaseTaskRunner, TaskConcurrencyType
from prefect.testing.utilities import exceptions_equal


class TaskRunnerStandardTestSuite(ABC):
    """
    The standard test suite for task runners.

    An implementation of this class should exist for every task runner.
    The implementation should define a `task_runner` fixture that yields
    an instance of the task runner to test. Running the test suite
    implementation will execute the standard task runner tests
    against the yielded task runner instance.

    Example:
    ```python
    import pytest

    from prefect.testing.standard_test_suites import TaskRunnerStandardTestSuite


    class TestSequentialTaskRunner(TaskRunnerStandardTestSuite):
        @pytest.fixture
        def task_runner(self):
            yield SequentialTaskRunner()
    ```
    """

    @pytest.fixture
    @abstractmethod
    def task_runner(self) -> BaseTaskRunner:
        pass

    async def test_successful_flow_run(self, task_runner):
        @task
        def task_a():
            return "a"

        @task
        def task_b():
            return "b"

        @task
        def task_c(b):
            return b + "c"

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            a = task_a()
            b = task_b()
            c = task_c(b)
            return a, b, c

        a, b, c = test_flow()
        assert (a, b, c) == ("a", "b", "bc")

    def test_failing_flow_run(self, task_runner):
        @task
        def task_a():
            raise RuntimeError("This task fails!")

        @task
        def task_b():
            raise ValueError("This task fails and passes data downstream!")

        @task
        def task_c(b):
            # This task attempts to use the upstream data and should fail too
            return b + "c"

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            a = task_a.submit()
            b = task_b.submit()
            c = task_c.submit(b)
            d = task_c.submit(c)

            return a, b, c, d

        state = test_flow._run()

        assert state.is_failed()
        a, b, c, d = state.result(raise_on_failure=False)
        with pytest.raises(RuntimeError, match="This task fails!"):
            a.result()
        with pytest.raises(
            ValueError, match="This task fails and passes data downstream"
        ):
            b.result()

        assert c.is_pending()
        assert c.name == "NotReady"
        assert (
            f"Upstream task run '{b.state_details.task_run_id}' did not reach a 'COMPLETED' state"
            in c.message
        )

        assert d.is_pending()
        assert d.name == "NotReady"
        assert (
            f"Upstream task run '{c.state_details.task_run_id}' did not reach a 'COMPLETED' state"
            in d.message
        )

    @pytest.fixture
    def tmp_file(self, tmp_path):
        tmp_file = tmp_path / "canary.txt"
        tmp_file.touch()
        return tmp_file

    def test_sync_tasks_run_sequentially_with_sequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        def foo():
            time.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow()

        assert tmp_file.read_text() == "bar"

    @pytest.mark.flaky(max_runs=4)  # Threads do not consistently yield
    def test_sync_tasks_run_concurrently_with_nonsequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        def foo():
            time.sleep(self.get_sleep_time())
            # Yield again in case the sleep started before the other thread was aready
            time.sleep(0)
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo.submit()
            bar.submit()

        test_flow()

        assert tmp_file.read_text() == "foo"

    async def test_async_tasks_run_sequentially_with_sequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo.submit()
            await bar.submit()

        await test_flow()

        assert tmp_file.read_text() == "bar"

    async def test_async_tasks_run_concurrently_with_nonsequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo.submit()
            await bar.submit()

        await test_flow()

        assert tmp_file.read_text() == "foo"

    async def test_async_tasks_run_concurrently_with_task_group_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo.submit)
                tg.start_soon(bar.submit)

        await test_flow()

        assert tmp_file.read_text() == "foo"

    def test_sync_subflows_run_sequentially_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @flow
        def foo():
            time.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow()

        assert tmp_file.read_text() == "bar"

    async def test_async_subflows_run_sequentially_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo()
            await bar()

        await test_flow()

        assert tmp_file.read_text() == "bar"

    async def test_async_subflows_run_concurrently_with_task_group_with_all_concurrency_types(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo)
                tg.start_soon(bar)

        await test_flow()

        assert tmp_file.read_text() == "foo"

    async def test_is_pickleable_after_start(self, task_runner):
        """
        The task_runner must be picklable as it is attached to `PrefectFuture` objects
        """
        async with task_runner.start():
            pickled = cloudpickle.dumps(task_runner)
            unpickled = cloudpickle.loads(pickled)
            assert isinstance(unpickled, type(task_runner))

    async def test_submit_and_wait(self, task_runner):
        task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

        async def fake_orchestrate_task_run(example_kwarg):
            return State(
                type=StateType.COMPLETED,
                data=DataDocument.encode("json", example_kwarg),
            )

        async with task_runner.start():
            fut = await task_runner.submit(
                task_run=task_run,
                run_key=f"{task_run.name}-{task_run.id.hex}",
                run_fn=fake_orchestrate_task_run,
                run_kwargs=dict(example_kwarg=1),
            )
            assert isinstance(fut, PrefectFuture), "submit should return a future"
            assert fut.task_run == task_run, "the future should have the same task run"
            assert fut.asynchronous == True

            state = await task_runner.wait(fut, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert state.result() == 1

    @pytest.mark.parametrize("exception", [KeyboardInterrupt(), ValueError("test")])
    async def test_wait_captures_exceptions_as_crashed_state(
        self, task_runner, exception
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.PARALLEL:
            pytest.skip(
                f"This will abort the run for {task_runner.concurrency_type} task runners."
            )

        task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

        async def fake_orchestrate_task_run():
            raise exception

        async with task_runner.start():
            future = await task_runner.submit(
                task_run=task_run,
                run_key=f"{task_run.name}-{task_run.id.hex}",
                run_fn=fake_orchestrate_task_run,
                run_kwargs={},
            )

            state = await task_runner.wait(future, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert state.name == "Crashed"
            result = state.result(raise_on_failure=False)

        assert exceptions_equal(result, exception)

    # These tests use a simple canary file to indicate if a items in a flow have run
    # sequentially or concurrently.
    # foo writes 'foo' to the file after sleeping for a little bit
    # bar writes 'bar' to the file immediately
    # If they run concurrently, 'foo' will be the final content of the file
    # If they run sequentially, 'bar' will be the final content of the file
    def get_sleep_time(self):
        """
        Amount of time to sleep before writing 'foo'
        A larger value will decrease brittleness but increase test times
        """
        sleep_time = 0.25

        if sys.platform != "darwin":
            # CI machines are slow
            sleep_time += 2.0

        if sys.version_info < (3, 8):
            # Python 3.7 is slower
            sleep_time += 0.5

        return sleep_time

    @pytest.fixture
    def tmp_file(self, tmp_path):
        tmp_file = tmp_path / "canary.txt"
        tmp_file.touch()
        return tmp_file

    def test_sync_tasks_run_sequentially_with_sequential_task_runners(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        def foo():
            time.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo.submit()
            bar.submit()

        test_flow()

        assert tmp_file.read_text() == "bar"

    def test_sync_tasks_run_concurrently_with_parallel_task_runners(
        self, task_runner, tmp_file, tmp_path
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.PARALLEL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        def foo():
            # Sleeping should yield to other threads
            time.sleep(self.get_sleep_time())
            # Perform an extra yield in case the bar thread was not ready
            time.sleep(0)
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo.submit()
            bar.submit()

        test_flow()

        assert tmp_file.read_text() == "foo"

    async def test_async_tasks_run_sequentially_with_sequential_task_runners(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo.submit()
            await bar.submit()

        await test_flow()

        assert tmp_file.read_text() == "bar"

    async def test_async_tasks_run_concurrently_with_parallel_task_runners(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.PARALLEL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task runners."
            )

        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo.submit()
            await bar.submit()

        await test_flow()

        assert tmp_file.read_text() == "foo"

    async def test_async_tasks_run_concurrently_with_task_group_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo.submit)
                tg.start_soon(bar.submit)

        await test_flow()

        assert tmp_file.read_text() == "foo"

    def test_sync_subflows_run_sequentially_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @flow
        def foo():
            time.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo._run()
            bar._run()

        test_flow()

        assert tmp_file.read_text() == "bar"

    async def test_async_subflows_run_sequentially_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo._run()
            await bar._run()

        await test_flow()

        assert tmp_file.read_text() == "bar"

    async def test_async_subflows_run_concurrently_with_task_group_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.get_sleep_time())
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo._run)
                tg.start_soon(bar._run)

        await test_flow()

        assert tmp_file.read_text() == "foo"
