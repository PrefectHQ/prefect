import httpx
import pytest

from prefect.exceptions import ObjectNotFound
from prefect.server.schemas.actions import WorkPoolUpdate
from prefect.server.schemas.core import WorkPool
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.workers.process import ProcessWorker

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


class TestCreate:
    @pytest.fixture(autouse=True)
    async def mock_collection_registry(self, respx_mock):
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

    async def test_create_work_pool(self, orion_client, mock_collection_registry):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name}",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert client_res.base_job_template == {}
        assert isinstance(client_res, WorkPool)

    async def test_default_template(self, orion_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name}",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.base_job_template == dict()

    async def test_default_paused(self, orion_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name}",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.is_paused is False

    async def test_paused_true(self, orion_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --paused",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.is_paused is True

    async def test_create_work_pool_from_registry(self, orion_client):
        pool_name = "fake-work"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --type fake",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert client_res.base_job_template == FAKE_DEFAULT_BASE_JOB_TEMPLATE
        assert client_res.type == "fake"
        assert isinstance(client_res, WorkPool)

    async def test_create_process_work_pool(self, orion_client):
        pool_name = "process-work"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --type process",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert (
            client_res.base_job_template
            == ProcessWorker.get_default_base_job_template()
        )
        assert client_res.type == "process"
        assert isinstance(client_res, WorkPool)

    def test_create_with_unsupported_type(self):
        invoke_and_assert(
            ["work-pool", "create", "my-pool", "--type", "unsupported"],
            expected_code=1,
            expected_output_contains=[
                "Unknown work pool type 'unsupported'.",
                "Please choose from",
                "process",
                "prefect-agent",
                "fake",
            ],
        )


class TestInspect:
    async def test_inspect(self, orion_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool inspect {work_pool.name!r}",
        )
        assert res.exit_code == 0
        assert work_pool.name in res.output
        assert work_pool.type in res.output
        assert str(work_pool.id) in res.output


class TestPause:
    async def test_pause(self, orion_client, work_pool):
        assert work_pool.is_paused is False
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool pause {work_pool.name}",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(work_pool.name)
        assert client_res.is_paused is True


class TestSetConcurrencyLimit:
    async def test_set_concurrency_limit(self, orion_client, work_pool):
        assert work_pool.concurrency_limit is None
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool set-concurrency-limit {work_pool.name} 10",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(work_pool.name)
        assert client_res.concurrency_limit == 10


class TestClearConcurrencyLimit:
    async def test_clear_concurrency_limit(self, orion_client, work_pool):
        await orion_client.update_work_pool(
            work_pool_name=work_pool.name,
            work_pool=WorkPoolUpdate(concurrency_limit=10),
        )
        work_pool = await orion_client.read_work_pool(work_pool.name)
        assert work_pool.concurrency_limit == 10

        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool clear-concurrency-limit {work_pool.name}",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(work_pool.name)
        assert client_res.concurrency_limit is None


class TestResume:
    async def test_resume(self, orion_client, work_pool):
        assert work_pool.is_paused is False

        # set paused
        await orion_client.update_work_pool(
            work_pool_name=work_pool.name,
            work_pool=WorkPoolUpdate(is_paused=True),
        )
        work_pool = await orion_client.read_work_pool(work_pool.name)
        assert work_pool.is_paused is True

        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool resume {work_pool.name}",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(work_pool.name)
        assert client_res.is_paused is False


class TestDelete:
    async def test_delete(self, orion_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool delete {work_pool.name}",
        )
        assert res.exit_code == 0
        with pytest.raises(ObjectNotFound):
            await orion_client.read_work_pool(work_pool.name)


class TestLS:
    async def test_ls(self, orion_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool ls",
        )
        assert res.exit_code == 0

    async def test_verbose(self, orion_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool ls --verbose",
        )
        assert res.exit_code == 0


class TestPreview:
    async def test_preview(self, orion_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool preview {work_pool.name}",
        )
        assert res.exit_code == 0
