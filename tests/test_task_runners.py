import warnings
from unittest.mock import MagicMock
from uuid import uuid4

import cloudpickle
import distributed
import pytest

# Import the local 'tests' module to pickle to ray workers
from prefect import flow, task
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.states import DataDocument, State, StateType
from prefect.task_runners import (
    ConcurrentTaskRunner,
    DaskTaskRunner,
    SequentialTaskRunner,
    TaskConcurrencyType,
)
from prefect.testing.standard_test_suites import TaskRunnerStandardTestSuite


@pytest.fixture
@pytest.mark.service("dask")
def dask_task_runner_with_existing_cluster(use_hosted_orion):
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


@pytest.fixture
@pytest.mark.service("ray")
def default_ray_task_runner():
    pytest.importorskip("ray", reason=RAY_MISSING_REASON)

    with warnings.catch_warnings():
        # Ray does not properly close resources and we do not want their warnings to
        # bubble into our test suite
        # https://github.com/ray-project/ray/pull/22419
        warnings.simplefilter("ignore", ResourceWarning)

        yield RayTaskRunner()


async def test_task_runner_cannot_be_started_while_running():
    async with SequentialTaskRunner().start() as task_runner:
        with pytest.raises(RuntimeError, match="already started"):
            async with task_runner.start():
                pass


class TestSequentialTaskRunner(TaskRunnerStandardTestSuite):
    @pytest.fixture
    def task_runner(self):
        yield SequentialTaskRunner()


class TestConcurrentTaskRunner(TaskRunnerStandardTestSuite):
    @pytest.fixture
    def task_runner(self):
        yield ConcurrentTaskRunner()


@pytest.mark.service("dask")
class TestDaskTaskRunner(TaskRunnerStandardTestSuite):
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

    async def test_is_pickleable_after_start(self, task_runner):
        """
        The task_runner must be picklable as it is attached to `PrefectFuture` objects
        Reimplemented to set Dask client as default to allow unpickling
        """
        task_runner.client_kwargs["set_as_default"] = True
        async with task_runner.start():
            pickled = cloudpickle.dumps(task_runner)
            unpickled = cloudpickle.loads(pickled)
            assert isinstance(unpickled, type(task_runner))

    @pytest.mark.parametrize("exception", [KeyboardInterrupt(), ValueError("test")])
    async def test_wait_captures_exceptions_as_crashed_state(
        self, task_runner, exception
    ):
        """
        Dask wraps the exception, interrupts will result in "Cancelled" tasks
        or "Killed" workers while normal errors will result in the raw error with Dask.
        We care more about the crash detection and
        lack of re-raise here than the equality of the exception.
        """
        if task_runner.concurrency_type != TaskConcurrencyType.PARALLEL:
            pytest.skip(
                f"This will abort the run for {task_runner.concurrency_type} task runners."
            )

        task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

        async def fake_orchestrate_task_run():
            raise exception

        async with task_runner.start():
            future = await task_runner.submit(
                task_run=task_run, run_fn=fake_orchestrate_task_run, run_kwargs={}
            )

            state = await task_runner.wait(future, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert state.name == "Crashed"


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

    @pytest.mark.service("dask")
    async def test_converts_prefect_futures_to_dask_futures(self):
        task_run_1 = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="1")
        task_run_2 = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="2")

        async def fake_orchestrate_task_run(example_kwarg):
            return State(
                type=StateType.COMPLETED,
                data=DataDocument.encode("cloudpickle", example_kwarg),
            )

        async with DaskTaskRunner().start() as task_runner:
            fut_1 = await task_runner.submit(
                task_run=task_run_1,
                run_fn=fake_orchestrate_task_run,
                run_kwargs=dict(example_kwarg=1),
            )

            original_submit = task_runner._client.submit
            mock = task_runner._client.submit = MagicMock(side_effect=original_submit)

            fut_2 = await task_runner.submit(
                task_run=task_run_2,
                run_fn=fake_orchestrate_task_run,
                run_kwargs=dict(example_kwarg=fut_1),
            )

            called_with = mock.call_args[1].get("example_kwarg")
            assert isinstance(
                called_with, distributed.Future
            ), "Prefect future converted to Dask future"
            assert called_with == task_runner._get_dask_future(fut_1)

            state_1 = await task_runner.wait(fut_1, 5)

            state_2 = await task_runner.wait(fut_2, 5)
            assert state_2.result() == state_1, "Dask converted the future to the state"
