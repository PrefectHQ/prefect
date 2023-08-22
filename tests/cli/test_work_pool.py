import sys

import httpx
import pytest
import readchar
from typer import Exit

from prefect.client.schemas.actions import WorkPoolUpdate
from prefect.client.schemas.objects import WorkPool
from prefect.exceptions import ObjectNotFound
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


@pytest.fixture
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.work_pool.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


@pytest.fixture(autouse=True)
def reset_cache():
    from prefect.server.api.collections import GLOBAL_COLLECTIONS_VIEW_CACHE

    GLOBAL_COLLECTIONS_VIEW_CACHE.clear()


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

    async def test_create_work_pool(self, prefect_client, mock_collection_registry):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t prefect-agent",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert client_res.base_job_template == {}
        assert isinstance(client_res, WorkPool)

    async def test_create_work_pool_with_empty_name(
        self, prefect_client, mock_collection_registry
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool create '' -t prefect-agent",
            expected_code=1,
            expected_output_contains=["name cannot be empty"],
        )

    async def test_create_work_pool_name_conflict(
        self, prefect_client, mock_collection_registry
    ):
        pool_name = "my-pool"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t prefect-agent",
            expected_code=0,
            expected_output_contains=[f"Created work pool {pool_name!r}"],
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t prefect-agent",
            expected_code=1,
            expected_output_contains=[
                f"Work pool named {pool_name!r} already exists. Please try creating"
                " your work pool again with a different name."
            ],
        )

    async def test_default_template(self, prefect_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t prefect-agent",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.base_job_template == dict()

    async def test_default_paused(self, prefect_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t prefect-agent",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.is_paused is False

    async def test_paused_true(self, prefect_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --paused -t prefect-agent",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.is_paused is True

    async def test_create_work_pool_from_registry(self, prefect_client):
        pool_name = "fake-work"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --type fake",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert client_res.base_job_template == FAKE_DEFAULT_BASE_JOB_TEMPLATE
        assert client_res.type == "fake"
        assert isinstance(client_res, WorkPool)

    async def test_create_process_work_pool(self, prefect_client):
        pool_name = "process-work"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --type process",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await prefect_client.read_work_pool(pool_name)
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

    def test_create_non_interactive_missing_args(self):
        invoke_and_assert(
            ["work-pool", "create", "no-type"],
            expected_code=1,
            expected_output=(
                "When not using an interactive terminal, you must supply a `--type`"
                " value."
            ),
        )

    @pytest.mark.usefixtures("interactive_console")
    async def test_create_interactive_first_type(self, prefect_client):
        work_pool_name = "test-interactive"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["work-pool", "create", work_pool_name],
            expected_code=0,
            user_input=readchar.key.ENTER,
            expected_output_contains=[f"Created work pool {work_pool_name!r}"],
        )
        client_res = await prefect_client.read_work_pool(work_pool_name)
        assert client_res.name == work_pool_name
        assert client_res.type == "prefect-agent"
        assert isinstance(client_res, WorkPool)

    @pytest.mark.usefixtures("interactive_console")
    async def test_create_interactive_second_type(self, prefect_client):
        work_pool_name = "test-interactive"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["work-pool", "create", work_pool_name],
            expected_code=0,
            user_input=readchar.key.DOWN + readchar.key.ENTER,
            expected_output_contains=[f"Created work pool {work_pool_name!r}"],
        )
        client_res = await prefect_client.read_work_pool(work_pool_name)
        assert client_res.name == work_pool_name
        assert client_res.type == "fake"
        assert isinstance(client_res, WorkPool)


class TestInspect:
    async def test_inspect(self, prefect_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool inspect {work_pool.name!r}",
        )
        assert res.exit_code == 0
        assert work_pool.name in res.output
        assert work_pool.type in res.output
        assert str(work_pool.id) in res.output


class TestPause:
    async def test_pause(self, prefect_client, work_pool):
        assert work_pool.is_paused is False
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool pause {work_pool.name}",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.is_paused is True


class TestSetConcurrencyLimit:
    async def test_set_concurrency_limit(self, prefect_client, work_pool):
        assert work_pool.concurrency_limit is None
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool set-concurrency-limit {work_pool.name} 10",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.concurrency_limit == 10


class TestClearConcurrencyLimit:
    async def test_clear_concurrency_limit(self, prefect_client, work_pool):
        await prefect_client.update_work_pool(
            work_pool_name=work_pool.name,
            work_pool=WorkPoolUpdate(concurrency_limit=10),
        )
        work_pool = await prefect_client.read_work_pool(work_pool.name)
        assert work_pool.concurrency_limit == 10

        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool clear-concurrency-limit {work_pool.name}",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.concurrency_limit is None


class TestResume:
    async def test_resume(self, prefect_client, work_pool):
        assert work_pool.is_paused is False

        # set paused
        await prefect_client.update_work_pool(
            work_pool_name=work_pool.name,
            work_pool=WorkPoolUpdate(is_paused=True),
        )
        work_pool = await prefect_client.read_work_pool(work_pool.name)
        assert work_pool.is_paused is True

        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool resume {work_pool.name}",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.is_paused is False


class TestDelete:
    async def test_delete(self, prefect_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool delete {work_pool.name}",
        )
        assert res.exit_code == 0
        with pytest.raises(ObjectNotFound):
            await prefect_client.read_work_pool(work_pool.name)


class TestLS:
    async def test_ls(self, prefect_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool ls",
        )
        assert res.exit_code == 0

    async def test_verbose(self, prefect_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool ls --verbose",
        )
        assert res.exit_code == 0


class TestPreview:
    async def test_preview(self, prefect_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool preview {work_pool.name}",
        )
        assert res.exit_code == 0
