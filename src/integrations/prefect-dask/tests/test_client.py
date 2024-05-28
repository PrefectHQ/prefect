import pytest
from prefect_dask.client import PrefectDaskClient

from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    TaskRunFilter,
    TaskRunFilterId,
)
from prefect.client.schemas.objects import TaskRunResult
from prefect.client.schemas.sorting import TaskRunSort
from prefect.context import FlowRunContext
from prefect.flows import flow
from prefect.tasks import task
from prefect.testing.fixtures import (  # noqa: F401
    hosted_api_server,
    use_hosted_api_server,
)

pytestmark = pytest.mark.usefixtures("use_hosted_api_server")


class TestSubmit:
    async def test_with_task(self):
        flow_run_id = None

        @task
        def test_task():
            return 42

        @flow
        def test_flow():
            nonlocal flow_run_id
            flow_run_id = FlowRunContext.get().flow_run.id
            with PrefectDaskClient() as client:
                future = client.submit(test_task)
                return future.result()

        assert test_flow() == 42

        prefect_client = get_client()
        assert flow_run_id is not None
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run_id]))
        )
        assert len(task_runs) == 1

    async def test_with_function(self):
        def func():
            return 42

        with PrefectDaskClient() as client:
            future = client.submit(func)
            assert future.result() == 42

    async def test_tracks_dependencies(self):
        flow_run_id = None

        @task
        def test_task(x):
            return x

        @flow
        def test_flow():
            nonlocal flow_run_id
            flow_run_id = FlowRunContext.get().flow_run.id
            with PrefectDaskClient() as client:
                future1 = client.submit(test_task, 42)
                future2 = client.submit(test_task, future1)
                return future2.result()

        assert test_flow() == 42

        prefect_client = get_client()
        assert flow_run_id is not None
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run_id])),
            sort=TaskRunSort.END_TIME_DESC,
        )
        assert len(task_runs) == 2
        assert task_runs[0].task_inputs == {"x": [TaskRunResult(id=task_runs[1].id)]}


class TestMap:
    async def test_with_task(self):
        flow_run_id = None

        @task
        def test_task(x):
            return x

        @flow
        def test_flow():
            nonlocal flow_run_id
            flow_run_id = FlowRunContext.get().flow_run.id
            with PrefectDaskClient() as client:
                futures = client.map(test_task, [1, 2, 3])
                return [future.result() for future in futures]

        assert test_flow() == [1, 2, 3]

        prefect_client = get_client()
        assert flow_run_id is not None
        task_runs = await prefect_client.read_task_runs(
            flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[flow_run_id]))
        )
        assert len(task_runs) == 3

    async def test_with_function(self):
        def func(x):
            return x

        with PrefectDaskClient() as client:
            futures = client.map(func, [1, 2, 3])
            assert [future.result() for future in futures] == [1, 2, 3]

    async def test_tracks_dependencies(self):
        flow_run_id = None

        @task
        def test_task(x):
            return x

        @flow
        def test_flow():
            nonlocal flow_run_id
            flow_run_id = FlowRunContext.get().flow_run.id
            with PrefectDaskClient() as client:
                future1 = client.submit(test_task, 42)
                future2 = client.submit(test_task, 42)
                future3 = client.submit(test_task, 42)
                futures = client.map(test_task, [future1, future2, future3])
                return [future.result() for future in futures], [
                    future.task_run_id for future in futures
                ]

        result, task_run_ids = test_flow()
        assert result == [42, 42, 42]

        prefect_client = get_client()
        assert flow_run_id is not None
        task_runs = await prefect_client.read_task_runs(
            task_run_filter=TaskRunFilter(id=TaskRunFilterId(any_=task_run_ids)),
            sort=TaskRunSort.END_TIME_DESC,
        )
        for task_run in task_runs:
            # difficult to deterministically assert the order of task runs, so we'll check to make sure
            # each task run has a single input
            assert len(task_run.task_inputs["x"]) == 1
