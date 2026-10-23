import httpx
import pytest
import respx

from prefect.utilities.dispatch import get_registry_for_type
from prefect.workers.base import BaseWorker
from prefect.workers.process import ProcessWorker
from prefect.workers.utilities import (
    get_available_work_pool_types,
    get_default_base_job_template_for_infrastructure_type,
    get_locally_installed_worker_metadata,
)

pytestmark = pytest.mark.clear_db

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

    @pytest.fixture
    def only_process_worker_installed(self, monkeypatch):
        monkeypatch.setattr(
            BaseWorker, "get_all_available_worker_types", lambda: ["process"]
        )

    @pytest.mark.usefixtures("mock_collection_registry_not_available")
    async def test_get_available_work_pool_types_without_collection_registry(
        self, monkeypatch, only_process_worker_installed, in_memory_prefect_client
    ):
        # `only_process_worker_installed` comes before the client, because the
        # client's server builds its local worker metadata when it starts.
        # Otherwise it would also list the worker classes other tests define.
        monkeypatch.setattr(
            "prefect.client.collections.get_client",
            lambda *args, **kwargs: in_memory_prefect_client,
        )

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


class TestGetLocallyInstalledWorkerMetadata:
    @pytest.fixture(autouse=True)
    def restore_worker_registry(self):
        """Defining a worker class registers its type for the whole process, so
        the workers these tests define are removed again afterwards."""
        registry = get_registry_for_type(BaseWorker)
        registered = dict(registry)
        yield
        registry.clear()
        registry.update(registered)

    def test_metadata_is_keyed_by_collection_then_worker_type(self):
        metadata = get_locally_installed_worker_metadata()

        assert metadata["prefect"]["process"]["type"] == "process"

    def test_metadata_matches_the_registry_view_shape(self):
        process = get_locally_installed_worker_metadata()["prefect"]["process"]

        assert process == {
            "type": "process",
            "display_name": ProcessWorker.get_display_name(),
            "description": ProcessWorker.get_description(),
            "documentation_url": ProcessWorker.get_documentation_url(),
            "logo_url": ProcessWorker.get_logo_url(),
            "install_command": "pip install prefect",
            "default_base_job_configuration": (
                ProcessWorker.get_default_base_job_template()
            ),
            "is_beta": False,
        }

    def test_collection_name_derived_from_the_worker_module(self, monkeypatch):
        class ArmadaWorker(ProcessWorker):
            type: str = "armada"
            _display_name = "Armada"

        ArmadaWorker.__module__ = "prefect_armada.worker"

        monkeypatch.setattr(
            BaseWorker, "get_all_available_worker_types", lambda: ["armada"]
        )
        monkeypatch.setattr(
            BaseWorker, "get_worker_class_from_type", lambda type: ArmadaWorker
        )

        metadata = get_locally_installed_worker_metadata()

        assert metadata["prefect-armada"]["armada"]["display_name"] == "Armada"
        assert (
            metadata["prefect-armada"]["armada"]["install_command"]
            == "pip install prefect-armada"
        )

    def test_a_worker_whose_metadata_fails_does_not_hide_the_others(
        self, monkeypatch, caplog
    ):
        class BrokenWorker(ProcessWorker):
            type: str = "broken"

            @classmethod
            def get_default_base_job_template(cls):
                raise RuntimeError("cannot build template")

        workers = {"broken": BrokenWorker, "process": ProcessWorker}
        monkeypatch.setattr(
            BaseWorker, "get_all_available_worker_types", lambda: list(workers)
        )
        monkeypatch.setattr(BaseWorker, "get_worker_class_from_type", workers.get)

        metadata = get_locally_installed_worker_metadata()

        assert list(metadata["prefect"]) == ["process"]
        [record] = [r for r in caplog.records if "'broken' worker" in r.getMessage()]
        assert record.name == "prefect.workers.utilities"

    def test_unregistered_worker_types_are_skipped(self, monkeypatch):
        monkeypatch.setattr(
            BaseWorker, "get_all_available_worker_types", lambda: ["gone"]
        )
        monkeypatch.setattr(BaseWorker, "get_worker_class_from_type", lambda type: None)

        assert get_locally_installed_worker_metadata() == {}
