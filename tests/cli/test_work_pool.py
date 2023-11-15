import sys
from pathlib import Path

import httpx
import pytest
import readchar
from typer import Exit

from prefect.client.schemas.actions import WorkPoolUpdate
from prefect.client.schemas.objects import WorkPool
from prefect.context import get_settings_context
from prefect.exceptions import ObjectNotFound
from prefect.settings import PREFECT_DEFAULT_WORK_POOL_NAME, load_profile
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.workers.base import BaseWorker
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

    async def test_create_work_pool_with_base_job_template(
        self, prefect_client, mock_collection_registry
    ):
        pool_name = "my-olympic-pool"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "work-pool",
                "create",
                pool_name,
                "--type",
                "process",
                "--base-job-template",
                Path(__file__).parent / "base-job-templates" / "process-worker.json",
            ],
            expected_code=0,
            expected_output_contains="Created work pool 'my-olympic-pool'",
        )

        client_res = await prefect_client.read_work_pool(pool_name)
        assert isinstance(client_res, WorkPool)
        assert client_res.name == pool_name
        assert client_res.base_job_template == {
            "job_configuration": {"command": "{{ command }}", "name": "{{ name }}"},
            "variables": {
                "properties": {
                    "command": {
                        "description": "Command to run.",
                        "title": "Command",
                        "type": "string",
                    },
                    "name": {
                        "description": "Description.",
                        "title": "Name",
                        "type": "string",
                    },
                },
                "type": "object",
            },
        }

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

    def test_create_with_unsupported_type(self, monkeypatch):
        def available():
            return ["process"]

        monkeypatch.setattr(BaseWorker, "get_all_available_worker_types", available)

        invoke_and_assert(
            ["work-pool", "create", "my-pool", "--type", "unsupported"],
            expected_code=1,
            expected_output=(
                "Unknown work pool type 'unsupported'. Please choose from fake,"
                " prefect-agent, process."
            ),
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

    async def test_create_set_as_default(self, prefect_client):
        settings_context = get_settings_context()
        assert (
            settings_context.profile.settings.get(PREFECT_DEFAULT_WORK_POOL_NAME)
            is None
        )
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t process --set-as-default",
            expected_output_contains=[
                f"Created work pool {pool_name!r}",
                (
                    f"Set {pool_name!r} as default work pool for profile"
                    f" {settings_context.profile.name!r}\n"
                ),
            ],
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert isinstance(client_res, WorkPool)

        # reload the profile to pick up change
        profile = load_profile(settings_context.profile.name)
        assert profile.settings.get(PREFECT_DEFAULT_WORK_POOL_NAME) == pool_name


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


class TestUpdate:
    async def test_update_description(self, prefect_client, work_pool):
        assert work_pool.description is None
        assert work_pool.type is not None
        assert work_pool.base_job_template is not None
        assert work_pool.is_paused is not None
        assert work_pool.concurrency_limit is None

        metamorphosis = (
            "One morning, as Gregor Samsa was waking up from anxious dreams, he"
            " discovered that in bed he had been changed into a monstrous verminous"
            " bug."
        )

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "work-pool",
                "update",
                work_pool.name,
                "--description",
                metamorphosis,
            ],
            expected_code=0,
            expected_output=f"Updated work pool '{work_pool.name}'",
        )

        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.description == metamorphosis
        # assert all other fields unchanged
        assert client_res.name == work_pool.name
        assert client_res.type == work_pool.type
        assert client_res.base_job_template == work_pool.base_job_template
        assert client_res.is_paused == work_pool.is_paused
        assert client_res.concurrency_limit == work_pool.concurrency_limit

    async def test_update_concurrency_limit(self, prefect_client, work_pool):
        assert work_pool.description is None
        assert work_pool.type is not None
        assert work_pool.base_job_template is not None
        assert work_pool.is_paused is not None
        assert work_pool.concurrency_limit is None

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "work-pool",
                "update",
                work_pool.name,
                "--concurrency-limit",
                123456,
            ],
            expected_code=0,
            expected_output=f"Updated work pool '{work_pool.name}'",
        )

        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.concurrency_limit == 123456
        # assert all other fields unchanged
        assert client_res.name == work_pool.name
        assert client_res.description == work_pool.description
        assert client_res.type == work_pool.type
        assert client_res.base_job_template == work_pool.base_job_template
        assert client_res.is_paused == work_pool.is_paused

        # Verify that the concurrency limit is unmodified when changing another
        # setting
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "work-pool",
                "update",
                work_pool.name,
                "--description",
                "Hello world lorem ipsum",
            ],
            expected_code=0,
            expected_output=f"Updated work pool '{work_pool.name}'",
        )

        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.concurrency_limit == 123456
        assert client_res.description == "Hello world lorem ipsum"
        # assert all other fields unchanged
        assert client_res.name == work_pool.name
        assert client_res.type == work_pool.type
        assert client_res.base_job_template == work_pool.base_job_template
        assert client_res.is_paused == work_pool.is_paused

    async def test_update_base_job_template(self, prefect_client, work_pool):
        assert work_pool.description is None
        assert work_pool.type is not None
        assert work_pool.base_job_template is not None
        assert work_pool.is_paused is not None
        assert work_pool.concurrency_limit is None

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "work-pool",
                "update",
                work_pool.name,
                "--base-job-template",
                Path(__file__).parent / "base-job-templates" / "process-worker.json",
            ],
            expected_code=0,
            expected_output=f"Updated work pool '{work_pool.name}'",
        )

        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.base_job_template != work_pool.base_job_template
        assert client_res.base_job_template == {
            "job_configuration": {"command": "{{ command }}", "name": "{{ name }}"},
            "variables": {
                "type": "object",
                "properties": {
                    "name": {
                        "title": "Name",
                        "description": "Description.",
                        "type": "string",
                    },
                    "command": {
                        "title": "Command",
                        "description": "Command to run.",
                        "type": "string",
                    },
                },
            },
        }
        # assert all other fields unchanged
        assert client_res.name == work_pool.name
        assert client_res.description == work_pool.description
        assert client_res.type == work_pool.type
        assert client_res.is_paused == work_pool.is_paused
        assert client_res.concurrency_limit == work_pool.concurrency_limit

    async def test_update_multi(self, prefect_client, work_pool):
        assert work_pool.description is None
        assert work_pool.type is not None
        assert work_pool.base_job_template is not None
        assert work_pool.is_paused is not None
        assert work_pool.concurrency_limit is None

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "work-pool",
                "update",
                work_pool.name,
                "--description",
                "Foo bar baz",
                "--concurrency-limit",
                300,
            ],
            expected_code=0,
            expected_output=f"Updated work pool '{work_pool.name}'",
        )

        client_res = await prefect_client.read_work_pool(work_pool.name)
        assert client_res.description == "Foo bar baz"
        assert client_res.concurrency_limit == 300
        # assert all other fields unchanged
        assert client_res.name == work_pool.name
        assert client_res.type == work_pool.type
        assert client_res.base_job_template == work_pool.base_job_template
        assert client_res.is_paused == work_pool.is_paused


class TestPreview:
    async def test_preview(self, prefect_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool preview {work_pool.name}",
        )
        assert res.exit_code == 0


class TestGetDefaultBaseJobTemplate:
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

    async def test_unknown_type(self, mock_collection_registry, monkeypatch):
        def available():
            return ["process"]

        monkeypatch.setattr(BaseWorker, "get_all_available_worker_types", available)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["work-pool", "get-default-base-job-template", "--type", "foobar"],
            expected_code=1,
            expected_output=(
                "Unknown work pool type 'foobar'. Please choose from fake,"
                " prefect-agent, process."
            ),
        )

    async def test_stdout(self, mock_collection_registry):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["work-pool", "get-default-base-job-template", "--type", "fake"],
            expected_code=0,
            expected_output_contains="fake_var",
        )

    async def test_file(self, mock_collection_registry, tmp_path):
        file = tmp_path / "out.json"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "work-pool",
                "get-default-base-job-template",
                "--type",
                "fake",
                "--file",
                file,
            ],
            expected_code=0,
        )

        contents = file.read_text()
        assert "job_configuration" in contents
        assert len(contents) == 211
