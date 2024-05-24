import prefect_dask.client
import pytest

from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
)
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
            with prefect_dask.client.PrefectDistributedClient() as client:
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

        with prefect_dask.client.PrefectDistributedClient() as client:
            future = client.submit(func)
            assert future.result() == 42


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
            with prefect_dask.client.PrefectDistributedClient() as client:
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

        with prefect_dask.client.PrefectDistributedClient() as client:
            futures = client.map(func, [1, 2, 3])
            assert [future.result() for future in futures] == [1, 2, 3]
