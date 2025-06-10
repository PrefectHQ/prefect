import asyncio
import time
from typing import Generator, List

import dask.dataframe as dd
import distributed
import pandas as pd
import pytest
from distributed import LocalCluster
from prefect_dask import DaskTaskRunner
from prefect_dask.task_runners import PrefectDaskFuture

from prefect import flow, task
from prefect.assets import Asset, materialize
from prefect.client.orchestration import get_client
from prefect.context import get_run_context
from prefect.futures import as_completed
from prefect.server.schemas.states import StateType
from prefect.states import State


@pytest.fixture(scope="module")
def cluster() -> Generator[distributed.LocalCluster, None, None]:
    with distributed.LocalCluster(dashboard_address=None) as cluster:
        yield cluster


@pytest.fixture
def dask_task_runner_with_existing_cluster(cluster: distributed.LocalCluster):  # noqa
    """
    Generate a dask task runner that's connected to a local cluster
    """
    yield DaskTaskRunner(cluster=cluster)


@pytest.fixture
def dask_task_runner_with_existing_cluster_address(cluster: distributed.LocalCluster):  # noqa
    """
    Generate a dask task runner that's connected to a local cluster
    """
    with distributed.Client(cluster) as client:
        address = client.scheduler.address
        yield DaskTaskRunner(address=address)


@pytest.fixture
def dask_task_runner_with_process_pool():  # noqa
    yield DaskTaskRunner(cluster_kwargs={"processes": True, "dashboard_address": None})


@pytest.fixture
def dask_task_runner_with_thread_pool():  # noqa
    yield DaskTaskRunner(cluster_kwargs={"processes": False, "dashboard_address": None})


@pytest.fixture
def default_dask_task_runner():  # noqa
    yield DaskTaskRunner(
        cluster_kwargs={
            "dashboard_address": None,  # Prevent port conflicts
        }
    )


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
    def task_runner(
        self, request: pytest.FixtureRequest
    ) -> Generator[DaskTaskRunner, None, None]:
        fixture_name = request.param._fixture_function.__name__
        yield request.getfixturevalue(fixture_name)

    async def test_duplicate(self, task_runner: DaskTaskRunner):
        new = task_runner.duplicate()
        assert new == task_runner
        assert new is not task_runner

    async def test_successful_flow_run(self, task_runner: DaskTaskRunner):
        @task
        def task_a():
            return "a"

        @task
        def task_b():
            return "b"

        @task
        def task_c(b: str):
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

    async def test_failing_flow_run(self, task_runner: DaskTaskRunner):
        @task
        def task_a():
            raise RuntimeError("This task fails!")

        @task
        def task_b():
            raise ValueError("This task fails and passes data downstream!")

        @task
        def task_c(b: str):
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

    async def test_async_task_timeout(self, task_runner: DaskTaskRunner):
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

    def test_as_completed_yields_correct_order(self, task_runner):
        @task
        def sleep_task(seconds):
            time.sleep(seconds)
            return seconds

        timings = [1, 5, 10]
        with task_runner:
            done_futures = []
            futures = [
                task_runner.submit(
                    sleep_task, parameters={"seconds": seconds}, wait_for=[]
                )
                for seconds in reversed(timings)
            ]
            for future in as_completed(futures=futures):
                done_futures.append(future.result())
            assert done_futures == timings

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

        futures: list[PrefectDaskFuture[int]] = []

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
                task_runner.client  # trigger client creation
                assert task_runner._cluster._adapt_called

    def test_string_cluster_class_is_properly_instantiated(self):
        task_runner = DaskTaskRunner(cluster_class="distributed.LocalCluster")

        @task
        def test_task():
            return 42

        @flow(task_runner=task_runner)
        def test_flow():
            return test_task.submit()

        assert test_flow().result() == 42

    async def test_successful_dataframe_flow_run(self, task_runner: DaskTaskRunner):
        @task
        def task_a():
            return dd.DataFrame.from_dict(
                {"x": [1, 1, 1], "y": [2, 2, 2]}, npartitions=1
            )

        @task
        def task_b(ddf: dd.DataFrame):
            return ddf.sum()

        @task
        def task_c(ddf):
            return ddf.compute()

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            a = task_a.submit()
            b = task_b.submit(a)
            c = task_c.submit(b)

            return c.result()

        result = test_flow()

        assert result.equals(pd.Series([3, 6], index=["x", "y"]))

    class TestInputArguments:
        async def test_dataclasses_can_be_passed_to_task_runners(
            self, task_runner: DaskTaskRunner
        ):
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

    def test_nested_task_submission(self, task_runner):
        @task
        def nested_task():
            return "nested task"

        @task
        def parent_task():
            nested_task_future = nested_task.submit()
            assert isinstance(nested_task_future, PrefectDaskFuture)
            return nested_task_future.result()

        @flow(task_runner=task_runner)
        def umbrella_flow():
            future = parent_task.submit()
            assert isinstance(future, PrefectDaskFuture)
            return future.result()

        assert umbrella_flow() == "nested task"

    def test_state_dependencies_via_wait_for(self, task_runner):
        @task
        def task_a():
            return time.time()

        @task
        def task_b():
            return time.time()

        @flow(task_runner=task_runner)
        def test_flow() -> tuple[float, float]:
            a = task_a.submit()
            b = task_b.submit(wait_for=[a])
            return a.result(), b.result()

        a_time, b_time = test_flow()

        assert b_time > a_time, "task_b timestamp should be after task_a timestamp"

    def test_state_dependencies_via_wait_for_disparate_upstream_tasks(
        self, task_runner
    ):
        @task
        def task_a():
            return time.time()

        @task
        def task_b():
            return time.time()

        @task
        def task_c():
            return time.time()

        @flow(task_runner=task_runner)
        def test_flow() -> tuple[float, float, float]:
            a = task_a.submit()
            b = task_b.submit()
            c = task_c.submit(wait_for=[a, b])

            return a.result(), b.result(), c.result()

        a_time, b_time, c_time = test_flow()

        assert c_time > a_time and c_time > b_time

    async def test_performance_report_generation(self, tmp_path):
        report_path = tmp_path / "dask-report.html"
        task_runner_with_performance_report_path = DaskTaskRunner(
            performance_report_path=str(report_path)
        )

        @task
        def task_a():
            return "a"

        @task
        def task_b():
            return "b"

        @task
        def task_c(b):
            return b + "c"

        @flow(version="test", task_runner=task_runner_with_performance_report_path)
        def test_flow():
            a = task_a.submit()
            b = task_b.submit()
            c = task_c.submit(b)
            return a, b, c

        test_flow()

        assert report_path.exists()
        report_content = report_path.read_text()
        assert "Dask Performance Report" in report_content

    async def test_assets_with_task_runner(self, task_runner):
        upstream = Asset(key="s3://data/dask_raw")
        downstream = Asset(key="s3://data/dask_processed")

        @materialize(upstream)
        async def extract():
            return {"rows": 50}

        @materialize(downstream)
        async def load(d):
            return {"rows": d["rows"] * 2}

        @flow(version="test", task_runner=task_runner)
        async def pipeline():
            run_context = get_run_context()
            raw_data = extract.submit()
            processed = load.submit(raw_data)
            processed.wait()
            return run_context.flow_run.id

        flow_run_id = await pipeline()

        async with get_client() as client:
            for i in range(5):
                response = await client._client.post(
                    "/events/filter",
                    json={
                        "filter": {
                            "event": {"prefix": ["prefect.asset."]},
                            "related": {"id": [f"prefect.flow-run.{flow_run_id}"]},
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
                asset_events = data.get("events", [])
                if len(asset_events) >= 3:
                    break
                # give a little more time for
                # server to process events
                await asyncio.sleep(2)
            else:
                raise RuntimeError("Unable to get any events from server!")

        assert len(asset_events) == 3

        upstream_events = [
            e
            for e in asset_events
            if e.get("resource", {}).get("prefect.resource.id") == upstream.key
        ]
        downstream_events = [
            e
            for e in asset_events
            if e.get("resource", {}).get("prefect.resource.id") == downstream.key
        ]

        # Should have 2 events for upstream (1 materialization, 1 reference)
        assert len(upstream_events) == 2
        assert len(downstream_events) == 1

        # Separate upstream events by type
        upstream_mat_events = [
            e
            for e in upstream_events
            if e["event"] == "prefect.asset.materialization.succeeded"
        ]
        upstream_ref_events = [
            e for e in upstream_events if e["event"] == "prefect.asset.referenced"
        ]

        assert len(upstream_mat_events) == 1
        assert len(upstream_ref_events) == 1

        upstream_mat_event = upstream_mat_events[0]
        upstream_ref_event = upstream_ref_events[0]
        downstream_event = downstream_events[0]

        # confirm upstream materialization event
        assert upstream_mat_event["event"] == "prefect.asset.materialization.succeeded"
        assert upstream_mat_event["resource"]["prefect.resource.id"] == upstream.key

        # confirm upstream reference event
        assert upstream_ref_event["event"] == "prefect.asset.referenced"
        assert upstream_ref_event["resource"]["prefect.resource.id"] == upstream.key

        # confirm downstream events
        assert downstream_event["event"] == "prefect.asset.materialization.succeeded"
        assert downstream_event["resource"]["prefect.resource.id"] == downstream.key
        related_assets = [
            r
            for r in downstream_event["related"]
            if r.get("prefect.resource.role") == "asset"
        ]
        assert len(related_assets) == 1
        assert related_assets[0]["prefect.resource.id"] == upstream.key
