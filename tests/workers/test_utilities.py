import httpx
import pytest
import respx

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


@pytest.fixture(autouse=True)
def reset_cache():
    from prefect.server.api.collections import GLOBAL_COLLECTIONS_VIEW_CACHE

    GLOBAL_COLLECTIONS_VIEW_CACHE.clear()


@pytest.fixture
async def mock_collection_registry():
    with respx.mock as respx_mock:
        respx_mock.get(
            "https://raw.githubusercontent.com/PrefectHQ/"
            "prefect-collection-registry/main/views/aggregate-worker-metadata.json"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "prefect": {
                        "prefect-agent": {
                            "type": "prefect-agent",
                            "default_base_job_configuration": {},
                        }
                    },
                    "prefect-fake": {
                        "fake": {
                            "type": "fake",
                            "default_base_job_configuration": (
                                FAKE_DEFAULT_BASE_JOB_TEMPLATE
                            ),
                        }
                    },
                },
            )
        )
        yield


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
    async def test_get_available_work_pool_types(self):
        work_pool_types = await get_available_work_pool_types()

        assert "prefect-agent" in work_pool_types
        assert "fake" in work_pool_types
        assert "process" in work_pool_types

    @pytest.mark.usefixtures("mock_collection_registry_not_available")
    async def test_get_available_work_pool_types_without_collection_registry(self):
        respx.routes
        work_pool_types = await get_available_work_pool_types()

        assert "prefect-agent" not in work_pool_types
        assert "fake" not in work_pool_types
        assert "process" in work_pool_types


class TestGetDefaultBaseJobTemplateForInfrastructureType:
    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_get_default_base_job_template_for_local_registry(self):
        result = await get_default_base_job_template_for_infrastructure_type("process")
        assert result == ProcessWorker.get_default_base_job_template()

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_get_default_base_job_template_for_collection_registry(self):
        result = await get_default_base_job_template_for_infrastructure_type("fake")
        assert result == FAKE_DEFAULT_BASE_JOB_TEMPLATE

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_get_default_base_job_template_for_non_existent_infrastructure_type(
        self,
    ):
        result = await get_default_base_job_template_for_infrastructure_type(
            "non-existent"
        )
        assert result is None
