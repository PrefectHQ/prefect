import httpx
import pytest
import respx

from prefect.workers.base import BaseWorker
from prefect.workers.process import ProcessWorker
from prefect.workers.utilities import (
    get_available_work_pool_types,
    get_default_base_job_template_for_infrastructure_type,
)

FAKE_DEFAULT_BASE_JOB_TEMPLATE = {
    "job_configuration": {
        "fake": "{{ fake_var }}",
    },
    "variables": {
        "type": "object",
        "properties": {
            "fake_var": {
                "type": "string",
                "default": "fake",
            }
        },
    },
}


@pytest.fixture
async def mock_collection_registry_not_available():
    with respx.mock as respx_mock:
        respx_mock.get(
            "https://raw.githubusercontent.com/PrefectHQ/"
            "prefect-collection-registry/main/views/aggregate-worker-metadata.json"
        ).mock(return_value=httpx.Response(503))
        yield


class TestGetAvailableWorkPoolTypes:
    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_get_available_work_pool_types(self, monkeypatch):
        def available():
            return ["faker", "process"]

        monkeypatch.setattr(BaseWorker, "get_all_available_worker_types", available)

        work_pool_types = await get_available_work_pool_types()
        assert work_pool_types == [
            "cloud-run:push",
            "docker",
            "fake",
            "faker",
            "kubernetes",
            "process",
        ]

    @pytest.mark.usefixtures("mock_collection_registry_not_available")
    async def test_get_available_work_pool_types_without_collection_registry(
        self, monkeypatch, in_memory_prefect_client
    ):
        respx.routes

        def available():
            return ["process"]

        monkeypatch.setattr(
            "prefect.client.collections.get_client",
            lambda *args, **kwargs: in_memory_prefect_client,
        )
        monkeypatch.setattr(BaseWorker, "get_all_available_worker_types", available)

        work_pool_types = await get_available_work_pool_types()

        assert set(work_pool_types) == {
            "azure-container-instance",
            "cloud-run",
            "cloud-run-v2",
            "docker",
            "ecs",
            "kubernetes",
            "process",
            "vertex-ai",
        }


@pytest.mark.usefixtures("mock_collection_registry")
class TestGetDefaultBaseJobTemplateForInfrastructureType:
    async def test_get_default_base_job_template_for_local_registry(self):
        result = await get_default_base_job_template_for_infrastructure_type("process")
        assert result == ProcessWorker.get_default_base_job_template()

    async def test_get_default_base_job_template_for_collection_registry(self):
        result = await get_default_base_job_template_for_infrastructure_type("fake")
        assert result == FAKE_DEFAULT_BASE_JOB_TEMPLATE

    async def test_get_default_base_job_template_for_non_existent_infrastructure_type(
        self,
    ):
        result = await get_default_base_job_template_for_infrastructure_type(
            "non-existent"
        )
        assert result is None
