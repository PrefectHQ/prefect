import prefect_dask.client
import pytest

from prefect.client.orchestration import get_client
from prefect.flows import flow
from prefect.tasks import task
from prefect.testing.fixtures import (  # noqa: F401
    hosted_api_server,
    use_hosted_api_server,
)


class TestSubmit:
    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_with_task(self):
        @task
        def test_task():
            return 42

        @flow
        def test_flow():
            with prefect_dask.client.PrefectDistributedClient() as client:
                future = client.submit(test_task)
                return future.result()

        assert test_flow() == 42

        prefect_client = get_client()
        flow_runs = await prefect_client.read_flow_runs()
        assert len(flow_runs) == 1
        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 1
        assert task_runs[0].flow_run_id == flow_runs[0].id

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_with_function(self):
        def func():
            return 42

        with prefect_dask.client.PrefectDistributedClient() as client:
            future = client.submit(func)
            assert future.result() == 42

        prefect_client = get_client()
        task_runs = await prefect_client.read_task_runs()
        assert len(task_runs) == 0
