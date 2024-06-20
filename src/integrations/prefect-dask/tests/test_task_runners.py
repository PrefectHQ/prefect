import asyncio
import time
from typing import List

import distributed
import pytest
from distributed import LocalCluster
from prefect_dask import DaskTaskRunner

from prefect import flow, task
from prefect.server.schemas.states import StateType
from prefect.states import State
from prefect.testing.fixtures import (  # noqa: F401
    hosted_api_server,
    use_hosted_api_server,
)


@pytest.fixture
def dask_task_runner_with_existing_cluster(use_hosted_api_server):  # noqa
    """
    Generate a dask task runner that's connected to a local cluster
    """
    with distributed.LocalCluster(n_workers=2) as cluster:
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
def dask_task_runner_with_process_pool(use_hosted_api_server):  # noqa
    yield DaskTaskRunner(cluster_kwargs={"processes": True})


@pytest.fixture
def dask_task_runner_with_thread_pool(use_hosted_api_server):  # noqa
    yield DaskTaskRunner(cluster_kwargs={"processes": False})


@pytest.fixture
def default_dask_task_runner(use_hosted_api_server):  # noqa
    yield DaskTaskRunner()


class TestDaskTaskRunner:
    @pytest.fixture(
        params=[
            default_dask_task_runner,
            # Existing cluster works outside of tests, but fails with serialization errors in tests
            # dask_task_runner_with_existing_cluster, :TODO Fix serialization errors in these tests
            dask_task_runner_with_existing_cluster_address,
            dask_task_runner_with_process_pool,
            dask_task_runner_with_thread_pool,
        ]
    )
    def task_runner(self, request):
        yield request.getfixturevalue(
            request.param._pytestfixturefunction.name or request.param.__name__
        )

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
            a = task_a.submit()
            b = task_b.submit()
            c = task_c.submit(b)
            return a, b, c

        a, b, c = test_flow()
        assert await a.result() == "a"
        assert await b.result() == "b"
        assert await c.result() == "bc"

    async def test_failing_flow_run(self, task_runner):
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

        state = test_flow(return_state=True)

        assert state.is_failed()
        result = await state.result(raise_on_failure=False)
        a, b, c, d = result
        with pytest.raises(RuntimeError, match="This task fails!"):
            await a.result()
        with pytest.raises(
            ValueError, match="This task fails and passes data downstream"
        ):
            await b.result()

        assert c.is_pending()
        assert c.name == "NotReady"
        assert (
            f"Upstream task run '{b.state_details.task_run_id}' did not reach a"
            " 'COMPLETED' state" in c.message
        )

        assert d.is_pending()
        assert d.name == "NotReady"
        assert (
            f"Upstream task run '{c.state_details.task_run_id}' did not reach a"
            " 'COMPLETED' state" in d.message
        )

    async def test_async_tasks(self, task_runner):
        @task
        async def task_a():
            return "a"

        @task
        async def task_b():
            return "b"

        @task
        async def task_c(b):
            return b + "c"

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            a = task_a.submit()
            b = task_b.submit()
            c = task_c.submit(b)
            return a, b, c

        a, b, c = await test_flow()
        assert await a.result() == "a"
        assert await b.result() == "b"
        assert await c.result() == "bc"

    async def test_submit_and_wait(self, task_runner):
        @task
        async def task_a():
            return "a"

        async def fake_orchestrate_task_run(example_kwarg):
            return State(
                type=StateType.COMPLETED,
                data=example_kwarg,
            )

        with task_runner:
            future = task_runner.submit(task_a, parameters={}, wait_for=[])
            future.wait()
            state = future.state
            assert await state.result() == "a"

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
            a = my_timeout_task.submit()
            b = my_dependent_task.submit(a)
            c = my_independent_task.submit()

            return a, b, c

        state = await test_flow(return_state=True)

        assert state.is_failed()
        ax, bx, cx = await state.result(raise_on_failure=False)
        assert ax.type == StateType.FAILED
        assert bx.type == StateType.PENDING
        assert cx.type == StateType.COMPLETED

    async def test_sync_task_timeout(self, task_runner):
        @task(timeout_seconds=1)
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

        state = test_flow(return_state=True)

        assert state.is_failed()
        ax, bx, cx = await state.result(raise_on_failure=False)
        assert ax.type == StateType.FAILED
        assert bx.type == StateType.PENDING
        assert cx.type == StateType.COMPLETED

    async def test_wait_captures_exceptions_as_crashed_state(self, task_runner):
        """
        Dask wraps the exception, interrupts will result in "Cancelled" tasks
        or "Killed" workers while normal errors will result in the raw error with Dask.
        We care more about the crash detection and
        lack of re-raise here than the equality of the exception.
        """
        if "processes" in task_runner.cluster_kwargs:
            pytest.skip("This will abort the run for a Dask cluster using processes.")

        @task
        def task_a():
            raise KeyboardInterrupt()

        with task_runner:
            future = task_runner.submit(
                task=task_a,
                parameters={},
                wait_for=[],
            )

            future.wait()
            assert future.state.type == StateType.CRASHED

    def test_dask_task_key_has_prefect_task_name(self):
        task_runner = DaskTaskRunner()

        @task
        def my_task():
            return 1

        futures = []

        @flow(task_runner=task_runner)
        def my_flow():
            futures.append(my_task.submit())
            futures.append(my_task.submit())
            futures.append(my_task.submit())

        my_flow()
        # ensure task run name is in key
        assert all(
            future.wrapped_future.key.startswith("my_task-") for future in futures
        )

    async def test_dask_cluster_adapt_is_properly_called(self):
        # mock of cluster instances with synchronous adapt method like
        # dask_kubernetes.classic.kubecluster.KubeCluster
        class MockDaskCluster(LocalCluster):
            def __init__(self, asynchronous: bool = False):
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
            with task_runner:
                assert task_runner._cluster._adapt_called

    def test_warns_if_future_garbage_collection_before_resolving(
        self, caplog, task_runner
    ):
        @task
        def test_task():
            return 42

        @flow(task_runner=task_runner)
        def test_flow():
            for _ in range(10):
                test_task.submit()

        test_flow()

        assert "A future was garbage collected before it resolved" in caplog.text

    def test_does_not_warn_if_future_resolved_when_garbage_collected(
        self, task_runner, caplog
    ):
        @task
        def test_task():
            return 42

        @flow(task_runner=task_runner)
        def test_flow():
            futures = [test_task.submit() for _ in range(10)]
            for future in futures:
                future.wait()

        test_flow()

        assert "A future was garbage collected before it resolved" not in caplog.text

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
