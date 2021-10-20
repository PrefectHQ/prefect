import sys
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock

import time

import anyio
import cloudpickle
import distributed
import pytest

from prefect import flow, task
from prefect.context import get_run_context
from prefect.executors import DaskExecutor, SequentialExecutor, BaseExecutor
from prefect.futures import PrefectFuture
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType


@contextmanager
def dask_executor_with_existing_cluster():
    """
    Generate a dask executor that's connected to a local cluster
    """
    with distributed.LocalCluster(n_workers=2) as cluster:
        with distributed.Client(cluster) as client:
            address = client.scheduler.address
            yield DaskExecutor(address=address)


@contextmanager
def dask_executor_with_process_pool():
    yield DaskExecutor(cluster_kwargs={"processes": True})


@pytest.fixture
def executor(request):
    """
    An indirect fixture that expects to receive one of the following
    - executor instance
    - executor type
    - callable generator that yields an executor instance

    Returns an executor instance that can be used in the test
    """
    if isinstance(request.param, BaseExecutor):
        yield request.param

    elif isinstance(request.param, type) and issubclass(request.param, BaseExecutor):
        yield request.param()

    elif callable(request.param):
        with request.param() as executor:
            yield executor

    else:
        raise TypeError(
            "Received invalid executor parameter. Expected executor type, instance, "
            f"or callable generator. Received {type(request.param).__name__}"
        )


parameterize_with_all_executors = pytest.mark.parametrize(
    "executor",
    [
        DaskExecutor,
        SequentialExecutor,
        dask_executor_with_existing_cluster,
        dask_executor_with_process_pool,
    ],
    indirect=True,
)


parameterize_with_parallel_executors = pytest.mark.parametrize(
    "executor",
    [
        DaskExecutor,
        dask_executor_with_existing_cluster,
    ],
    indirect=True,
)


parameterize_with_sequential_executors = pytest.mark.parametrize(
    "executor",
    [SequentialExecutor],
    indirect=True,
)


@parameterize_with_all_executors
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


@parameterize_with_all_executors
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
def test_subflow_run_by_executor_pairing(parent_executor, child_executor):
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


class TestExecutorParallelism:
    """
    These tests use a simple canary file to indicate if a items in a flow have run
    sequentially or concurrently.

    foo writes 'foo' to the file after sleeping for a little bit
    bar writes 'bar' to the file immediately

    If they run concurrently, 'foo' will be the final content of the file
    If they run sequentially, 'bar' will be the final content of the file
    """

    # Amount of time to sleep before writing 'foo'
    # A larger value will decrease brittleness but increase test times
    SLEEP_TIME = 0.25

    @pytest.fixture
    def tmp_file(self, tmp_path):
        tmp_file = tmp_path / "canary.txt"
        tmp_file.touch()
        return tmp_file

    @parameterize_with_sequential_executors
    def test_sync_tasks_run_sequentially_with_sequential_executors(
        self, executor, tmp_file
    ):
        @task
        def foo():
            time.sleep(self.SLEEP_TIME)
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

    @parameterize_with_parallel_executors
    def test_sync_tasks_run_concurrently_with_parallel_executors(
        self, executor, tmp_file
    ):
        @task
        def foo():
            time.sleep(self.SLEEP_TIME)
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

    @parameterize_with_sequential_executors
    async def test_async_tasks_run_sequentially_with_sequential_executors(
        self, executor, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
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

    @parameterize_with_parallel_executors
    async def test_async_tasks_run_concurrently_with_parallel_executors(
        self, executor, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
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

    @parameterize_with_all_executors
    async def test_async_tasks_run_concurrently_with_task_group_with_all_executors(
        self, executor, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
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

    @parameterize_with_all_executors
    def test_sync_subflows_run_sequentially_with_all_executors(
        self, executor, tmp_file
    ):
        @flow
        def foo():
            time.sleep(self.SLEEP_TIME)
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

    @parameterize_with_all_executors
    async def test_async_subflows_run_sequentially_with_all_executors(
        self, executor, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
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

    @parameterize_with_all_executors
    async def test_async_subflows_run_concurrently_with_task_group_with_all_executors(
        self, executor, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
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


@parameterize_with_all_executors
async def test_is_pickleable_after_start(executor):
    """
    The executor must be picklable as it is attached to `PrefectFuture` objects
    """
    if isinstance(executor, DaskExecutor):
        # We must set the dask client as the default for it to be unpicklable in the
        # main process
        executor.client_kwargs["set_as_default"] = True

    async with executor.start():
        pickled = cloudpickle.dumps(executor)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, type(executor))


@parameterize_with_all_executors
async def test_submit_and_wait(executor):
    task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

    async def fake_orchestrate_task_run(example_kwarg):
        return State(
            type=StateType.COMPLETED,
            data=DataDocument.encode("json", example_kwarg),
        )

    async with executor.start():
        fut = await executor.submit(
            task_run=task_run,
            run_fn=fake_orchestrate_task_run,
            run_kwargs=dict(example_kwarg=1),
        )
        assert isinstance(fut, PrefectFuture), "submit should return a future"
        assert fut.task_run == task_run, "the future should have the same task run"
        assert fut.asynchronous == True

        state = await executor.wait(fut)
        assert isinstance(state, State), "wait should return a state"
        assert state.result() == 1


class TestDaskExecutor:
    async def test_connect_to_running_cluster(self, monkeypatch):
        with distributed.Client(processes=False, set_as_default=False) as client:
            address = client.scheduler.address
            executor = DaskExecutor(address=address)
            assert executor.address == address

            monkeypatch.setattr("distributed.Client", AsyncMock())

            async with executor.start():
                pass

            distributed.Client.assert_called_once_with(
                address, **executor.client_kwargs
            )

    async def test_start_local_cluster(self, monkeypatch):
        executor = DaskExecutor(cluster_kwargs={"processes": False})
        assert executor.cluster_class == distributed.LocalCluster
        assert executor.cluster_kwargs == {
            "processes": False,
            "asynchronous": True,
        }

        monkeypatch.setattr("distributed.Client", AsyncMock())

        async with executor.start():
            pass

        distributed.Client.assert_called_once_with(
            executor._cluster, **executor.client_kwargs
        )

    async def test_adapt_kwargs(self, monkeypatch):
        adapt_kwargs = {"minimum": 1, "maximum": 1}
        monkeypatch.setattr("distributed.LocalCluster.adapt", MagicMock())

        executor = DaskExecutor(
            cluster_kwargs={"processes": False, "n_workers": 0},
            adapt_kwargs=adapt_kwargs,
        )
        assert executor.adapt_kwargs == adapt_kwargs

        async with executor.start():
            pass

        distributed.LocalCluster.adapt.assert_called_once_with(**adapt_kwargs)

    async def test_client_kwargs(self, monkeypatch):
        executor = DaskExecutor(
            client_kwargs={"set_as_default": True, "foo": "bar"},
        )
        assert executor.client_kwargs == {
            "set_as_default": True,
            "asynchronous": True,
            "foo": "bar",
        }

        monkeypatch.setattr("distributed.Client", AsyncMock())

        async with executor.start():
            pass

        distributed.Client.assert_called_once_with(
            executor._cluster, **executor.client_kwargs
        )

    async def test_cluster_class_string_is_imported(self):
        executor = DaskExecutor(
            cluster_class="distributed.deploy.spec.SpecCluster",
        )
        assert executor.cluster_class == distributed.deploy.spec.SpecCluster

    async def test_cluster_class_and_kwargs(self):

        init_method = MagicMock()

        # Define a custom cluster class that just calls a mock; wrap `LocalCluster` so
        # we don't have to actually implement anything
        class TestCluster(distributed.LocalCluster):
            def __init__(self, *args, **kwargs):
                init_method(*args, **kwargs)
                return super().__init__(asynchronous=True)

        executor = DaskExecutor(
            cluster_class=TestCluster,
            cluster_kwargs={"some_kwarg": "some_val"},
        )
        assert executor.cluster_class == TestCluster

        async with executor.start():
            pass

        init_method.assert_called_once()
        _, kwargs = init_method.call_args
        assert kwargs == {"some_kwarg": "some_val", "asynchronous": True}

    def test_cant_specify_both_address_and_cluster_class(self):
        with pytest.raises(ValueError):
            DaskExecutor(
                address="localhost:8787",
                cluster_class=distributed.LocalCluster,
            )
