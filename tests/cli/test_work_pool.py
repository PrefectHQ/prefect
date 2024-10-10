import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import readchar
from typer import Exit

from prefect.client.schemas.actions import WorkPoolUpdate
from prefect.client.schemas.objects import WorkPool
from prefect.context import get_settings_context
from prefect.exceptions import ObjectNotFound
from prefect.settings import (
    PREFECT_DEFAULT_WORK_POOL_NAME,
    PREFECT_UI_URL,
    load_profile,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.workers.base import BaseWorker
from prefect.workers.process import ProcessWorker

MOCK_PREFECT_UI_URL = "https://api.prefect.io"

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


class TestCreate:
    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_create_work_pool(self, prefect_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t fake",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name!r}" in res.output
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert client_res.base_job_template == FAKE_DEFAULT_BASE_JOB_TEMPLATE
        assert isinstance(client_res, WorkPool)

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_create_work_pool_with_base_job_template(
        self, prefect_client, mock_collection_registry
    ):
        pool_name = "my-olympic-pool"

        with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=[
                    "work-pool",
                    "create",
                    pool_name,
                    "--type",
                    "process",
                    "--base-job-template",
                    Path(__file__).parent
                    / "base-job-templates"
                    / "process-worker.json",
                ],
                expected_code=0,
                expected_output_contains=[
                    "Created work pool 'my-olympic-pool'",
                    "/work-pools/work-pool/",
                ],
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

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_create_work_pool_with_empty_name(
        self, prefect_client, mock_collection_registry
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool create '' -t process",
            expected_code=1,
            expected_output_contains=["name cannot be empty"],
        )

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_create_work_pool_name_conflict(
        self, prefect_client, mock_collection_registry
    ):
        pool_name = "my-pool"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t process",
            expected_code=0,
            expected_output_contains=[f"Created work pool {pool_name!r}"],
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t process",
            expected_code=1,
            expected_output_contains=[
                f"Work pool named {pool_name!r} already exists. Use --overwrite to update it."
            ],
        )

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_default_template(self, prefect_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t fake",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.base_job_template == FAKE_DEFAULT_BASE_JOB_TEMPLATE

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_default_paused(self, prefect_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t process",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.is_paused is False

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_paused_true(self, prefect_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --paused -t process",
        )
        assert res.exit_code == 0
        client_res = await prefect_client.read_work_pool(pool_name)
        assert client_res.is_paused is True

    @pytest.mark.usefixtures("mock_collection_registry")
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

    @pytest.mark.usefixtures("mock_collection_registry")
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

    @pytest.mark.usefixtures("mock_collection_registry")
    def test_create_with_unsupported_type(self, monkeypatch):
        invoke_and_assert(
            ["work-pool", "create", "my-pool", "--type", "unsupported"],
            expected_code=1,
            expected_output_contains=(
                "Unknown work pool type 'unsupported'. Please choose from "
            ),
        )

    @pytest.mark.usefixtures("mock_collection_registry")
    def test_create_non_interactive_missing_args(self):
        invoke_and_assert(
            ["work-pool", "create", "no-type"],
            expected_code=1,
            expected_output=(
                "When not using an interactive terminal, you must supply a `--type`"
                " value."
            ),
        )

    @pytest.mark.usefixtures("interactive_console", "mock_collection_registry")
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
        assert client_res.type == "fake"
        assert isinstance(client_res, WorkPool)

    @pytest.mark.usefixtures("interactive_console", "mock_collection_registry")
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
        assert client_res.type == "cloud-run:push"
        assert isinstance(client_res, WorkPool)

    @pytest.mark.usefixtures("mock_collection_registry")
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

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_create_with_provision_infra(self, monkeypatch):
        mock_provision = AsyncMock()

        class MockProvisioner:
            def __init__(self):
                self._console = None

            @property
            def console(self):
                return self._console

            @console.setter
            def console(self, value):
                self._console = value

            async def provision(self, *args, **kwargs):
                await mock_provision(*args, **kwargs)
                return FAKE_DEFAULT_BASE_JOB_TEMPLATE

        monkeypatch.setattr(
            "prefect.cli.work_pool.get_infrastructure_provisioner_for_work_pool_type",
            lambda *args: MockProvisioner(),
        )

        pool_name = "fake-work"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --type fake --provision-infra",
        )
        assert res.exit_code == 0

        assert mock_provision.await_count == 1

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_create_with_provision_infra_unsupported(self):
        pool_name = "fake-work"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --type fake --provision-infra",
        )
        assert res.exit_code == 0
        assert (
            "Automatic infrastructure provisioning is not supported for 'fake' work"
            " pools." in res.output
        )

    @pytest.mark.usefixtures("interactive_console", "mock_collection_registry")
    async def test_create_prompt_table_only_displays_push_pool_types_using_provision_infra_flag(
        self, prefect_client, monkeypatch
    ):
        mock_provision = AsyncMock()

        class MockProvisioner:
            def __init__(self):
                self._console = None

            @property
            def console(self):
                return self._console

            @console.setter
            def console(self, value):
                self._console = value

            async def provision(self, *args, **kwargs):
                await mock_provision(*args, **kwargs)
                return FAKE_DEFAULT_BASE_JOB_TEMPLATE

        monkeypatch.setattr(
            "prefect.cli.work_pool.get_infrastructure_provisioner_for_work_pool_type",
            lambda *args: MockProvisioner(),
        )

        await run_sync_in_worker_thread(
            invoke_and_assert,
            ["work-pool", "create", "test-interactive", "--provision-infra"],
            expected_code=0,
            user_input=readchar.key.ENTER,
            expected_output_contains=[
                "What type of work pool infrastructure would you like to use?",
                "Prefect Cloud Run: Push",
            ],
            expected_output_does_not_contain=[
                "Prefect Fake",
                "Prefect Agent",
            ],
        )

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_create_work_pool_with_overwrite(self, prefect_client):
        pool_name = "overwrite-pool"

        # Create initial work pool
        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --type process",
            expected_code=0,
            expected_output_contains=[f"Created work pool {pool_name!r}"],
        )

        initial_pool = await prefect_client.read_work_pool(pool_name)
        assert initial_pool.name == pool_name
        assert not initial_pool.is_paused

        # Attempt to overwrite the work pool (updating is_paused)
        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --paused --overwrite",
            expected_code=0,
            expected_output_contains=[f"Updated work pool {pool_name!r}"],
        )

        updated_pool = await prefect_client.read_work_pool(pool_name)
        assert updated_pool.name == pool_name
        assert updated_pool.id == initial_pool.id
        assert updated_pool.is_paused

        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --paused",
            expected_code=1,
            expected_output_contains=[
                f"Work pool named {pool_name!r} already exists. Use --overwrite to update it."
            ],
        )


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
        await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool delete {work_pool.name}",
            user_input="y",
            expected_code=0,
        )
        with pytest.raises(ObjectNotFound):
            await prefect_client.read_work_pool(work_pool.name)

    async def test_delete_non_existent(self, prefect_client):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool delete non-existent",
            expected_code=1,
            expected_output_contains="Work pool 'non-existent' does not exist.",
            expected_output_does_not_contain="Are you sure you want to delete work pool with name 'non-existent'?",
        )


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

    async def test_ls_with_zero_concurrency_limit(self, prefect_client, work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool set-concurrency-limit {work_pool.name} 0",
        )
        assert res.exit_code == 0
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            "work-pool ls",
        )
        assert "None" not in res.output


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
    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_unknown_type(self, monkeypatch):
        def available():
            return ["process"]

        monkeypatch.setattr(BaseWorker, "get_all_available_worker_types", available)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["work-pool", "get-default-base-job-template", "--type", "foobar"],
            expected_code=1,
            expected_output_contains=(
                "Unknown work pool type 'foobar'. Please choose from "
            ),
        )

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_stdout(self):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["work-pool", "get-default-base-job-template", "--type", "fake"],
            expected_code=0,
            expected_output_contains="fake_var",
        )

    @pytest.mark.usefixtures("mock_collection_registry")
    async def test_file(self, tmp_path):
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


class TestProvisionInfrastructure:
    async def test_provision_infra(self, monkeypatch, push_work_pool, prefect_client):
        client_res = await prefect_client.read_work_pool(push_work_pool.name)
        assert client_res.base_job_template != FAKE_DEFAULT_BASE_JOB_TEMPLATE

        mock_provision = AsyncMock()

        class MockProvisioner:
            def __init__(self):
                self._console = None

            @property
            def console(self):
                return self._console

            @console.setter
            def console(self, value):
                self._console = value

            async def provision(self, *args, **kwargs):
                await mock_provision(*args, **kwargs)
                return FAKE_DEFAULT_BASE_JOB_TEMPLATE

        monkeypatch.setattr(
            "prefect.cli.work_pool.get_infrastructure_provisioner_for_work_pool_type",
            lambda *args: MockProvisioner(),
        )

        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool provision-infra {push_work_pool.name}",
        )
        assert res.exit_code == 0

        assert mock_provision.await_count == 1

        # ensure work pool base job template was updated
        client_res = await prefect_client.read_work_pool(push_work_pool.name)
        assert client_res.base_job_template == FAKE_DEFAULT_BASE_JOB_TEMPLATE

    async def test_provision_infra_unsupported(self, push_work_pool):
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool provision-infrastructure {push_work_pool.name}",
        )
        assert res.exit_code == 0
        assert (
            "Automatic infrastructure provisioning is not supported for"
            " 'push-work-pool:push' work pools." in res.output
        )
