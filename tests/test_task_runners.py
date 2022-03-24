from unittest.mock import MagicMock

import distributed
import pytest

from prefect import flow, task
from prefect.task_runners import (
    ConcurrentTaskRunner,
    DaskTaskRunner,
    SequentialTaskRunner,
)
from prefect.utilities.testing import TaskRunnerTests, parameterize_with_fixtures


@pytest.fixture
@pytest.mark.service("dask")
def dask_task_runner_with_existing_cluster():
    """
    Generate a dask task runner that's connected to a local cluster
    """
    with distributed.LocalCluster(n_workers=2) as cluster:
        with distributed.Client(cluster) as client:
            address = client.scheduler.address
            yield DaskTaskRunner(address=address)


@pytest.fixture
@pytest.mark.service("dask")
def dask_task_runner_with_process_pool():
    yield DaskTaskRunner(cluster_kwargs={"processes": True})


@pytest.fixture
@pytest.mark.service("dask")
def dask_task_runner_with_thread_pool():
    yield DaskTaskRunner(cluster_kwargs={"processes": False})


@pytest.fixture
def distributed_client_init(monkeypatch):
    mock = MagicMock()

    class DistributedClient(distributed.Client):
        """
        A patched `distributed.Client` so we can inspect calls to `__init__`
        """

        def __init__(self, *args, **kwargs):
            mock(*args, **kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("distributed.Client", DistributedClient)
    return mock


@pytest.fixture
@pytest.mark.service("dask")
def default_dask_task_runner():
    yield DaskTaskRunner()


@pytest.fixture
def default_sequential_task_runner():
    yield SequentialTaskRunner()


@pytest.fixture
def default_concurrent_task_runner():
    yield ConcurrentTaskRunner()


async def test_task_runner_cannot_be_started_while_running():
    async with SequentialTaskRunner().start() as task_runner:
        with pytest.raises(RuntimeError, match="already started"):
            async with task_runner.start():
                pass


class TestSequentialTaskRunner(TaskRunnerTests):
    @pytest.fixture
    def task_runner(self):
        yield SequentialTaskRunner()


class TestConcurrentTaskRunner(TaskRunnerTests):
    @pytest.fixture
    def task_runner(self):
        yield ConcurrentTaskRunner()


class TestDaskTaskRunner(TaskRunnerTests):
    @pytest.fixture(
        params=[
            default_dask_task_runner,
            dask_task_runner_with_existing_cluster,
            dask_task_runner_with_process_pool,
            dask_task_runner_with_thread_pool,
        ]
    )
    def task_runner(self, request):
        yield request.getfixturevalue(
            request.param._pytestfixturefunction.name or request.param.__name__
        )


class TestDaskTaskRunnerConfig:
    @pytest.mark.service("dask")
    async def test_connect_to_running_cluster(self, distributed_client_init):
        with distributed.Client(processes=False, set_as_default=False) as client:
            address = client.scheduler.address
            task_runner = DaskTaskRunner(address=address)
            assert task_runner.address == address

            async with task_runner.start():
                pass

            distributed_client_init.assert_called_with(
                address, asynchronous=True, **task_runner.client_kwargs
            )

    @pytest.mark.service("dask")
    async def test_start_local_cluster(self, distributed_client_init):
        task_runner = DaskTaskRunner(cluster_kwargs={"processes": False})
        assert task_runner.cluster_class == None, "Default is delayed for import"
        assert task_runner.cluster_kwargs == {"processes": False}

        async with task_runner.start():
            pass

        assert task_runner.cluster_class == distributed.LocalCluster

        distributed_client_init.assert_called_with(
            task_runner._cluster, asynchronous=True, **task_runner.client_kwargs
        )

    @pytest.mark.service("dask")
    async def test_adapt_kwargs(self, monkeypatch):
        adapt_kwargs = {"minimum": 1, "maximum": 1}
        monkeypatch.setattr("distributed.LocalCluster.adapt", MagicMock())

        task_runner = DaskTaskRunner(
            cluster_kwargs={"processes": False, "n_workers": 0},
            adapt_kwargs=adapt_kwargs,
        )
        assert task_runner.adapt_kwargs == adapt_kwargs

        async with task_runner.start():
            pass

        distributed.LocalCluster.adapt.assert_called_once_with(**adapt_kwargs)

    @pytest.mark.service("dask")
    async def test_client_kwargs(self, distributed_client_init):
        task_runner = DaskTaskRunner(
            client_kwargs={"set_as_default": True, "connection_limit": 100},
        )
        assert task_runner.client_kwargs == {
            "set_as_default": True,
            "connection_limit": 100,
        }

        async with task_runner.start():
            pass

        distributed_client_init.assert_called_with(
            task_runner._cluster, asynchronous=True, **task_runner.client_kwargs
        )

    async def test_cluster_class_string_is_imported(self):
        task_runner = DaskTaskRunner(
            cluster_class="distributed.deploy.spec.SpecCluster",
        )
        assert task_runner.cluster_class == distributed.deploy.spec.SpecCluster

    @pytest.mark.service("dask")
    async def test_cluster_class_and_kwargs(self):

        init_method = MagicMock()

        # Define a custom cluster class that just calls a mock; wrap `LocalCluster` so
        # we don't have to actually implement anything
        class TestCluster(distributed.LocalCluster):
            def __init__(self, *args, **kwargs):
                init_method(*args, **kwargs)
                return super().__init__(asynchronous=True)

        task_runner = DaskTaskRunner(
            cluster_class=TestCluster,
            cluster_kwargs={"some_kwarg": "some_val"},
        )
        assert task_runner.cluster_class == TestCluster

        async with task_runner.start():
            pass

        init_method.assert_called_once()
        _, kwargs = init_method.call_args
        assert kwargs == {"some_kwarg": "some_val", "asynchronous": True}

    def test_cannot_specify_both_address_and_cluster_class(self):
        with pytest.raises(ValueError):
            DaskTaskRunner(
                address="localhost:8787",
                cluster_class=distributed.LocalCluster,
            )

    def test_cannot_specify_asynchronous(self):
        with pytest.raises(ValueError, match="`client_kwargs`"):
            DaskTaskRunner(client_kwargs={"asynchronous": True})

        with pytest.raises(ValueError, match="`cluster_kwargs`"):
            DaskTaskRunner(cluster_kwargs={"asynchronous": True})

    @pytest.mark.service("dask")
    def test_nested_dask_task_runners_warn_on_port_collision_but_succeeds(self):
        @task
        def idenitity(x):
            return x

        @flow(version="test", task_runner=DaskTaskRunner())
        def parent_flow():
            a = idenitity("a")
            return child_flow(a), a

        @flow(version="test", task_runner=DaskTaskRunner())
        def child_flow(a):
            return idenitity(a).wait().result()

        with pytest.warns(
            UserWarning,
            match="Port .* is already in use",
        ):
            task_state, subflow_state = parent_flow().result()
            assert task_state.result() == "a"
            assert subflow_state.result() == "a"
