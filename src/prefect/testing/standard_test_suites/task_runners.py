import asyncio
import os
import time
from abc import ABC, abstractmethod
from functools import partial
from uuid import uuid4

import anyio
import cloudpickle
import pytest

from prefect import flow, task
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import StateType
from prefect.logging import get_run_logger
from prefect.states import Crashed, State
from prefect.task_runners import BaseTaskRunner, TaskConcurrencyType
from prefect.testing.utilities import exceptions_equal
from prefect.utilities.annotations import allow_failure, quote


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

    @pytest.fixture
    def tmp_file(self, tmp_path):
        file_path = tmp_path / "canary.txt"
        file_path.touch()
        return file_path

    async def test_duplicate(self, task_runner):
        new = task_runner.duplicate()
        assert new == task_runner
        assert new is not task_runner

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
            f"Upstream task run '{b.state_details.task_run_id}' did not reach a"
            " 'COMPLETED' state"
            in c.message
        )

        assert d.is_pending()
        assert d.name == "NotReady"
        assert (
            f"Upstream task run '{c.state_details.task_run_id}' did not reach a"
            " 'COMPLETED' state"
            in d.message
        )

    def test_sync_tasks_run_sequentially_with_sequential_concurrency_type(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
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
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
            )

        @task
        def foo():
            time.sleep(self.get_sleep_time())
            # Yield again in case the sleep started before the other thread was already
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
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
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
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
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
                data=example_kwarg,
            )

        async with task_runner.start():
            await task_runner.submit(
                key=task_run.id,
                call=partial(fake_orchestrate_task_run, example_kwarg=1),
            )
            state = await task_runner.wait(task_run.id, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert await state.result() == 1

    @pytest.mark.parametrize("exception", [KeyboardInterrupt(), ValueError("test")])
    async def test_wait_captures_exceptions_as_crashed_state(
        self, task_runner, exception
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.PARALLEL:
            pytest.skip(
                f"This will abort the run for {task_runner.concurrency_type} task"
                " runners."
            )

        task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

        async def fake_orchestrate_task_run():
            raise exception

        async with task_runner.start():
            await task_runner.submit(
                key=task_run.id,
                call=fake_orchestrate_task_run,
            )

            state = await task_runner.wait(task_run.id, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert state.type == StateType.CRASHED
            result = await state.result(raise_on_failure=False)

        assert exceptions_equal(result, exception)

    async def test_async_task_timeout(self, task_runner):
        @task(timeout_seconds=0.1)
        async def my_timeout_task():
            await asyncio.sleep(2)
            return 42

        @task
        async def my_dependent_task(task_res):
            return 1764

        @task
        async def my_independent_task():
            return 74088

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            a = await my_timeout_task.submit()
            b = await my_dependent_task.submit(a)
            c = await my_independent_task.submit()

            return a, b, c

        state = await test_flow._run()

        assert state.is_failed()
        ax, bx, cx = await state.result(raise_on_failure=False)
        assert ax.type == StateType.FAILED
        assert bx.type == StateType.PENDING
        assert cx.type == StateType.COMPLETED

    def test_sync_task_timeout(self, task_runner):
        @task(timeout_seconds=0.1)
        def my_timeout_task():
            time.sleep(2)
            return 42

        @task
        def my_dependent_task(task_res):
            return 1764

        @task
        def my_independent_task():
            return 74088

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            a = my_timeout_task.submit()
            b = my_dependent_task.submit(a)
            c = my_independent_task.submit()

            return a, b, c

        state = test_flow._run()

        assert state.is_failed()
        ax, bx, cx = state.result(raise_on_failure=False)
        assert ax.type == StateType.FAILED
        assert bx.type == StateType.PENDING
        assert cx.type == StateType.COMPLETED

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

        if os.environ.get("CI"):
            # CI machines are slow
            sleep_time += 3

        return sleep_time

    def test_sync_tasks_run_sequentially_with_sequential_task_runners(
        self, task_runner, tmp_file
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
            pytest.skip(
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
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
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
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
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
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
                f"This test does not apply to {task_runner.concurrency_type} task"
                " runners."
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

    def test_allow_failure(self, task_runner, caplog):
        @task
        def failing_task():
            raise ValueError("This is expected")

        @task
        def depdendent_task():
            logger = get_run_logger()
            logger.info("Dependent task still runs!")
            return 1

        @task
        def another_dependent_task():
            logger = get_run_logger()
            logger.info("Sub-dependent task still runs!")
            return 1

        @flow(task_runner=task_runner)
        def test_flow():
            ft = failing_task.submit()
            dt = depdendent_task.submit(wait_for=[allow_failure(ft)])
            another_dependent_task.submit(wait_for=[dt])

        with pytest.raises(ValueError, match="This is expected"):
            test_flow()
            assert len(caplog.records) == 2
            assert caplog.records[0].msg == "Dependent task still runs!"
            assert caplog.records[1].msg == "Sub-dependent task still runs!"

    def test_passing_quoted_state(self, task_runner):
        @task
        def test_task():
            state = Crashed()
            return quote(state)

        @flow(task_runner=task_runner)
        def test_flow():
            return test_task()

        result = test_flow()
        assert isinstance(result, quote)
        assert isinstance(result.unquote(), State)
