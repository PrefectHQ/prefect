import sys
from unittest.mock import MagicMock
from uuid import uuid4
from contextlib import asynccontextmanager

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock

import cloudpickle
import distributed
import pytest

from prefect import flow, task
from prefect.context import get_run_context
from prefect.executors import DaskExecutor, SequentialExecutor
from prefect.orion.schemas.states import State, StateType
from prefect.orion.schemas.data import DataDocument
from prefect.futures import PrefectFuture
from prefect.orion.schemas.core import TaskRun


def get_test_flow():
    @task
    def task_a():
        print("Inside task_a.fn")
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test")
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        return a, b, c

    return test_flow


@pytest.mark.parametrize(
    "executor",
    [
        SequentialExecutor(),
        DaskExecutor(),
    ],
)
def test_flow_run_by_executor(executor):
    test_flow = get_test_flow()
    test_flow.executor = executor

    a, b, c = test_flow().result()
    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )


def get_failing_test_flow():
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

    @flow(version="test")
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)
        return a, b, c, d

    return test_flow


@pytest.mark.parametrize(
    "executor",
    [
        SequentialExecutor(),
        DaskExecutor(),
    ],
)
def test_failing_flow_run_by_executor(executor):
    test_flow = get_failing_test_flow()
    test_flow.executor = executor

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
    "executor",
    [
        SequentialExecutor(),
        # We must set the dask client as the default for it to be unpicklable in the
        # main process
        DaskExecutor(client_kwargs={"set_as_default": True}),
    ],
)
async def test_is_pickleable_after_start(executor):
    """
    The executor must be picklable as it is attached to `PrefectFuture` objects
    """
    async with executor.start():
        pickled = cloudpickle.dumps(executor)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, type(executor))


@asynccontextmanager
async def dask_executor_with_existing_cluster():
    """
    Generate a dask executor that's connected to a local cluster
    """
    with distributed.Client(processes=False, set_as_default=False) as client:
        address = client.scheduler.address
        yield DaskExecutor(address=address)


def wrap_in_context(value):
    """Simple utility for creating a static generator when required as an input"""

    @asynccontextmanager
    async def yield_value():
        yield value

    return yield_value


@pytest.mark.parametrize(
    "gen_executor",
    [
        wrap_in_context(SequentialExecutor()),
        wrap_in_context(DaskExecutor()),
        dask_executor_with_existing_cluster,
    ],
)
async def test_submit_and_wait(gen_executor):
    async with gen_executor() as executor:
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
