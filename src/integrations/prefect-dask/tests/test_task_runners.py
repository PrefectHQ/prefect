import asyncio
import logging
import sys
from functools import partial
from typing import List
from uuid import uuid4

import cloudpickle
import distributed
import pytest
from distributed import LocalCluster
from distributed.scheduler import KilledWorker
from prefect_dask import DaskTaskRunner

import prefect.engine
from prefect import flow, get_run_logger, task
from prefect.client.schemas import TaskRun
from prefect.server.schemas.states import StateType
from prefect.states import State
from prefect.task_runners import TaskConcurrencyType
from prefect.testing.fixtures import (  # noqa: F401
    hosted_api_server,
    use_hosted_api_server,
)
from prefect.testing.standard_test_suites import TaskRunnerStandardTestSuite
from prefect.testing.utilities import exceptions_equal


@pytest.fixture(scope="session")
def event_loop(request):
    """
    Redefine the event loop to support session/module-scoped fixtures;
    see https://github.com/pytest-dev/pytest-asyncio/issues/68
    When running on Windows we need to use a non-default loop for subprocess support.
    """
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    policy = asyncio.get_event_loop_policy()

    if sys.version_info < (3, 8) and sys.platform != "win32":
        from prefect.utilities.compat import ThreadedChildWatcher

        # Python < 3.8 does not use a `ThreadedChildWatcher` by default which can
        # lead to errors in tests as the previous default `SafeChildWatcher`  is not
        # compatible with threaded event loops.
        policy.set_child_watcher(ThreadedChildWatcher())

    loop = policy.new_event_loop()

    # configure asyncio logging to capture long running tasks
    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.setLevel("WARNING")
    asyncio_logger.addHandler(logging.StreamHandler())
    loop.set_debug(True)
    loop.slow_callback_duration = 0.25

    try:
        yield loop
    finally:
        loop.close()

    # Workaround for failures in pytest_asyncio 0.17;
    # see https://github.com/pytest-dev/pytest-asyncio/issues/257
    policy.set_event_loop(loop)


@pytest.fixture
async def dask_task_runner_with_existing_cluster(use_hosted_api_server):  # noqa
    """
    Generate a dask task runner that's connected to a local cluster
    """
    async with distributed.LocalCluster(n_workers=2, asynchronous=True) as cluster:
        yield DaskTaskRunner(cluster=cluster)


@pytest.fixture
def dask_task_runner_with_existing_cluster_address(use_hosted_api_server):  # noqa
    """
    Generate a dask task runner that's connected to a local cluster
    """
    with distributed.LocalCluster(n_workers=2) as cluster:
        with distributed.Client(cluster) as client:
            address = client.scheduler.address
            yield DaskTaskRunner(address=address)


@pytest.fixture
def dask_task_runner_with_process_pool():
    yield DaskTaskRunner(cluster_kwargs={"processes": True})


@pytest.fixture
def dask_task_runner_with_thread_pool():
    yield DaskTaskRunner(cluster_kwargs={"processes": False})


@pytest.fixture
def default_dask_task_runner():
    yield DaskTaskRunner()


class TestDaskTaskRunner(TaskRunnerStandardTestSuite):
    @pytest.fixture(
        params=[
            default_dask_task_runner,
            dask_task_runner_with_existing_cluster,
            dask_task_runner_with_existing_cluster_address,
            dask_task_runner_with_process_pool,
            dask_task_runner_with_thread_pool,
        ]
    )
    def task_runner(self, request):
        yield request.getfixturevalue(
            request.param._pytestfixturefunction.name or request.param.__name__
        )

    def test_sync_task_timeout(self, task_runner):
        """
        This test is inherited from the prefect testing module and it may not
        appropriately skip on Windows. Here we skip it explicitly.
        """
        if sys.platform.startswith("win"):
            pytest.skip("cancellation due to timeouts is not supported on Windows")
        super().test_async_task_timeout(task_runner)

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
                f"This will abort the run for "
                f"{task_runner.concurrency_type} task runners."
            )

        task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

        async def fake_orchestrate_task_run():
            raise exception

        async with task_runner.start():
            await task_runner.submit(
                key=task_run.id,
                call=partial(fake_orchestrate_task_run),
            )

            state = await task_runner.wait(task_run.id, 5)
            assert state is not None, "wait timed out"
            assert isinstance(state, State), "wait should return a state"
            assert state.type == StateType.CRASHED

    @pytest.mark.parametrize(
        "exceptions",
        [
            (KeyboardInterrupt(), KilledWorker),
            (ValueError("test"), ValueError),
        ],
    )
    async def test_exception_to_crashed_state_in_flow_run(
        self, exceptions, task_runner, monkeypatch
    ):
        if task_runner.concurrency_type != TaskConcurrencyType.PARALLEL:
            pytest.skip(
                f"This will abort the run for "
                f"{task_runner.concurrency_type} task runners."
            )

        (raised_exception, state_exception_type) = exceptions

        def throws_exception_before_task_begins(
            task,
            task_run,
            parameters,
            wait_for,
            result_factory,
            settings,
            *args,
            **kwds,
        ):
            """
            Simulates an exception occurring while a remote task runner is attempting
            to unpickle and run a Prefect task.
            """
            raise raised_exception

        monkeypatch.setattr(
            prefect.engine, "begin_task_run", throws_exception_before_task_begins
        )

        @task()
        def test_task():
            logger = get_run_logger()
            logger.info("Dask should raise an exception before this task runs.")

        @flow(task_runner=task_runner)
        def test_flow():
            future = test_task.submit()
            future.wait(10)

        # ensure that the type of exception raised by the flow matches the type of
        # exception we expected the task runner to receive.
        with pytest.raises(state_exception_type) as exc:
            await test_flow()
            # If Dask passes the same exception type back, it should pass
            # the equality check
            if type(raised_exception) == state_exception_type:
                assert exceptions_equal(raised_exception, exc)

    def test_cluster_not_asynchronous(self):
        with pytest.raises(ValueError, match="The cluster must have"):
            with distributed.LocalCluster(n_workers=2) as cluster:
                DaskTaskRunner(cluster=cluster)

    def test_dask_task_key_has_prefect_task_name(self):
        task_runner = DaskTaskRunner()

        @task
        def my_task():
            return 1

        @flow(task_runner=task_runner)
        def my_flow():
            my_task.submit()
            my_task.submit()
            my_task.submit()

        my_flow()
        futures = task_runner._dask_futures.values()
        # ensure task run name is in key
        assert all(future.key.startswith("my_task-") for future in futures)
        # ensure flow run retries is in key
        assert all(future.key.endswith("-1") for future in futures)

    async def test_dask_cluster_adapt_is_properly_called(self):
        # mock of cluster instances with synchronous adapt method like
        # dask_kubernetes.classic.kubecluster.KubeCluster
        class MockDaskCluster(LocalCluster):
            def __init__(self, asynchronous: bool):
                self._adapt_called = False
                super().__init__(asynchronous=asynchronous)

            def adapt(self, **kwargs):
                self._adapt_called = True

        # mock of cluster instances with asynchronous adapt method like
        # dask_kubernetes.operator.kubecluster.KubeCluster
        class AsyncMockDaskCluster(MockDaskCluster):
            async def adapt(self, **kwargs):
                self._adapt_called = True

        for task_runner_class in [MockDaskCluster, AsyncMockDaskCluster]:
            # the adapt_kwargs argument triggers the calls to the adapt method
            task_runner = DaskTaskRunner(
                cluster_class=task_runner_class,
                adapt_kwargs={"minimum": 1, "maximum": 1},
            )
            async with task_runner.start():
                assert task_runner._cluster._adapt_called

    async def test_task_runner_can_execute_sync_task_in_async_flow(self, task_runner):
        """
        This is a regression test for https://github.com/PrefectHQ/prefect/issues/7422
        """

        @task
        def identity(x):
            return x

        @flow(task_runner=task_runner)
        async def test_flow() -> int:
            mapped_futures = identity.map(range(1, 4))
            single_future = identity.submit(1)

            return sum([fut.result() for fut in mapped_futures + [single_future]])

        result = await test_flow()
        assert result == 7  # 1 + 2 + 3 + 1

    class TestInputArguments:
        async def test_dataclasses_can_be_passed_to_task_runners(self, task_runner):
            """
            this is a regression test for https://github.com/PrefectHQ/prefect/issues/6905
            """
            from dataclasses import dataclass

            @dataclass
            class Foo:
                value: int

            @task
            def get_dataclass_values(n: int):
                return [Foo(value=i) for i in range(n)]

            @task
            def print_foo(x: Foo) -> Foo:
                print(x)
                return x

            @flow(task_runner=task_runner)
            def test_dask_flow(n: int = 3) -> List[Foo]:
                foos = get_dataclass_values(n)
                future = print_foo.submit(foos[0])
                futures = print_foo.map(foos)

                return [fut.result() for fut in futures + [future]]

            results = test_dask_flow()

            assert results == [Foo(value=i) for i in range(3)] + [Foo(value=0)]
