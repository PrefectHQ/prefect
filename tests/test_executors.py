import pytest
import time
import anyio

from prefect import flow, task
from prefect.executors import DaskExecutor, SequentialExecutor
from prefect.context import get_run_context


@pytest.mark.parametrize(
    "executor",
    [
        SequentialExecutor(),
        DaskExecutor(),
    ],
)
def test_flow_run_by_executor(executor):
    @task
    def task_a():
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test", executor=executor)
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        return a, b, c

    a, b, c = test_flow().result()
    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )


@pytest.mark.parametrize(
    "executor",
    [
        SequentialExecutor(),
        DaskExecutor(),
    ],
)
def test_failing_flow_run_by_executor(executor):
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

    @flow(version="test", executor=executor)
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)
        return a, b, c, d

    state = test_flow()
    assert state.is_failed()
    a, b, c, d = state.result(raise_on_failure=False)
    with pytest.raises(RuntimeError, match="This task fails!"):
        a.result()
    with pytest.raises(ValueError, match="This task fails and passes data downstream"):
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


@pytest.mark.parametrize(
    "parent_executor,child_executor",
    [
        (SequentialExecutor(), DaskExecutor()),
        (DaskExecutor(), SequentialExecutor()),
    ],
)
def test_subflow_run_by_executor(parent_executor, child_executor):
    @task
    def task_a():
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test", executor=parent_executor)
    def parent_flow():
        assert get_run_context().executor is parent_executor
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = child_flow(c)
        return a, b, c, d

    @flow(version="test", executor=child_executor)
    def child_flow(c):
        assert get_run_context().executor is child_executor
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)
        return a, b, c, d

    a, b, c, d = parent_flow().result()
    # parent
    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )
    # child
    a, b, c, d = d.result()
    assert (a.result(), b.result(), c.result(), d.result()) == ("a", "b", "bc", "bcc")


SEQUENTIAL_EXECUTORS = [SequentialExecutor]
PARALLEL_EXECUTORS = [DaskExecutor]


class TestExecutorParallelism:
    """
    These tests use a simple canary file to indicate if a items in a flow have run
    sequentially or concurrently.

    foo writes 'foo' to the file after sleeping for a second
    bar writes 'bar' to the file immediately

    If they run concurrently, 'foo' will be the final content of the file
    If they run sequentially, 'bar' will be the final content of of the file
    """

    @pytest.fixture
    def tmp_file(self, tmp_path):
        tmp_file = tmp_path / "canary.txt"
        tmp_file.touch()
        return tmp_file

    @pytest.mark.parametrize("executor", SEQUENTIAL_EXECUTORS)
    def test_sync_tasks_run_sequentially(self, executor, tmp_file):
        @task
        def foo():
            time.sleep(1)
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "bar"

    @pytest.mark.parametrize("executor", PARALLEL_EXECUTORS)
    def test_sync_tasks_run_concurrently(self, executor, tmp_file):
        @task
        def foo():
            time.sleep(1)
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "foo"

    @pytest.mark.parametrize("executor", SEQUENTIAL_EXECUTORS)
    async def test_async_tasks_run_sequentially(self, executor, tmp_file):
        @task
        async def foo():
            await anyio.sleep(1)
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "bar"

    @pytest.mark.parametrize("executor", PARALLEL_EXECUTORS)
    async def test_async_tasks_run_concurrently(self, executor, tmp_file):
        @task
        async def foo():
            await anyio.sleep(1)
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"

    @pytest.mark.parametrize(
        # All executors should display concurrency when using task groups or gathering
        "executor",
        SEQUENTIAL_EXECUTORS + PARALLEL_EXECUTORS,
    )
    async def test_async_tasks_run_concurrently_with_task_group(
        self, executor, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(1)
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo)
                tg.start_soon(bar)

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"

    @pytest.mark.parametrize("executor", SEQUENTIAL_EXECUTORS + PARALLEL_EXECUTORS)
    def test_sync_subflows_run_sequentially(self, executor, tmp_file):
        @flow
        def foo():
            time.sleep(1)
            tmp_file.write_text("foo")

        @flow
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "bar"

    @pytest.mark.parametrize("executor", SEQUENTIAL_EXECUTORS + PARALLEL_EXECUTORS)
    async def test_async_subflows_run_sequentially(self, executor, tmp_file):
        @flow
        async def foo():
            await anyio.sleep(1)
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()
        assert tmp_file.read_text() == "bar"

    @pytest.mark.parametrize("executor", SEQUENTIAL_EXECUTORS + PARALLEL_EXECUTORS)
    async def test_async_subflows_run_concurrently_with_task_group(
        self, executor, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(1)
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", executor=executor)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo)
                tg.start_soon(bar)

        (await test_flow()).result()
        assert tmp_file.read_text() == "foo"
