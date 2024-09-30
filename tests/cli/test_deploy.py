import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import Optional
from unittest import mock
from uuid import UUID, uuid4

import pendulum
import pytest
import readchar
import yaml
from typer import Exit

import prefect
from prefect.blocks.system import JSON, Secret
from prefect.cli.deploy import (
    _check_for_matching_deployment_name_and_entrypoint_in_prefect_file,
    _create_deployment_triggers,
    _initialize_deployment_triggers,
)
from prefect.client.orchestration import PrefectClient, ServerType
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import WorkPool
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.deployments.base import (
    _save_deployment_to_prefect_file,
    initialize_project,
)
from prefect.deployments.steps.core import StepExecutionError
from prefect.events import (
    DeploymentCompoundTrigger,
    DeploymentEventTrigger,
    EventTrigger,
    Posture,
)
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.server.schemas.actions import (
    BlockDocumentCreate,
    BlockSchemaCreate,
    BlockTypeCreate,
)
from prefect.settings import (
    PREFECT_DEFAULT_WORK_POOL_NAME,
    PREFECT_EXPERIMENTAL_ENABLE_SCHEDULE_CONCURRENCY,
    PREFECT_UI_URL,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.filesystem import tmpchdir

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


@pytest.fixture
def enable_schedule_concurrency():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_SCHEDULE_CONCURRENCY: True}):
        yield


@pytest.fixture
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.deploy.is_interactive", lambda: True)

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


@pytest.fixture
def project_dir(tmp_path):
    with tmpchdir(tmp_path):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        initialize_project()
        yield tmp_path


@pytest.fixture
def project_dir_with_single_deployment_format(tmp_path):
    with tmpchdir(tmp_path):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        initialize_project()

        with open("prefect.yaml", "r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"][0]["schedule"] = None

        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(contents["deployments"][0], f)

        yield tmp_path


@pytest.fixture
def uninitialized_project_dir(project_dir):
    Path(project_dir, "prefect.yaml").unlink()
    return project_dir


@pytest.fixture
def uninitialized_project_dir_with_git_no_remote(uninitialized_project_dir):
    subprocess.run(["git", "init"], cwd=uninitialized_project_dir)
    assert Path(uninitialized_project_dir, ".git").exists()
    return uninitialized_project_dir


@pytest.fixture
def uninitialized_project_dir_with_git_with_remote(
    uninitialized_project_dir_with_git_no_remote,
):
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.com/org/repo.git"],
        cwd=uninitialized_project_dir_with_git_no_remote,
    )
    return uninitialized_project_dir_with_git_no_remote


@pytest.fixture
async def default_agent_pool(prefect_client):
    try:
        return await prefect_client.create_work_pool(
            WorkPoolCreate(name="default-agent-pool", type="prefect-agent")
        )
    except ObjectAlreadyExists:
        return await prefect_client.read_work_pool("default-agent-pool")


@pytest.fixture
async def docker_work_pool(prefect_client: PrefectClient) -> WorkPool:
    return await prefect_client.create_work_pool(
        work_pool=WorkPoolCreate(
            name="test-docker-work-pool",
            type="docker",
            base_job_template={
                "job_configuration": {"image": "{{ image}}"},
                "variables": {
                    "type": "object",
                    "properties": {
                        "image": {
                            "title": "Image",
                            "type": "string",
                        },
                    },
                },
            },
        )
    )


@pytest.fixture
async def mock_prompt(monkeypatch):
    # Mock prompts() where password=True to prevent hanging
    def new_prompt(message, password=False, **kwargs):
        if password:
            return "456"
        else:
            return original_prompt(message, password=password, **kwargs)

    original_prompt = prefect.cli._prompts.prompt
    monkeypatch.setattr("prefect.cli._prompts.prompt", new_prompt)


@pytest.fixture
def mock_provide_password(monkeypatch):
    def new_prompt(message, password=False, **kwargs):
        if password:
            return "my-token"
        else:
            return original_prompt(message, password=password, **kwargs)

    original_prompt = prefect.cli._prompts.prompt
    monkeypatch.setattr("prefect.cli.deploy.prompt", new_prompt)


@pytest.fixture
def mock_build_docker_image(monkeypatch):
    mock_build = mock.MagicMock()
    mock_build.return_value = {"build-image": {"image": "{{ build-image.image }}"}}

    monkeypatch.setattr(
        "prefect.deployments.steps.core.import_object",
        lambda x: mock_build,
    )
    monkeypatch.setattr(
        "prefect.deployments.steps.core.import_module",
        lambda x: None,
    )

    return mock_build


@pytest.fixture
async def aws_credentials(prefect_client):
    aws_credentials_type = await prefect_client.create_block_type(
        block_type=BlockTypeCreate(
            name="AWS Credentials",
            slug="aws-credentials",
        )
    )

    aws_credentials_schema = await prefect_client.create_block_schema(
        block_schema=BlockSchemaCreate(
            block_type_id=aws_credentials_type.id,
            fields={"properties": {"aws_access_key_id": {"type": "string"}}},
        )
    )

    return await prefect_client.create_block_document(
        block_document=BlockDocumentCreate(
            name="bezos-creds",
            block_type_id=aws_credentials_type.id,
            block_schema_id=aws_credentials_schema.id,
            data={"aws_access_key_id": "AKIA1234"},
        )
    )


@pytest.fixture
def set_ui_url():
    with temporary_settings({PREFECT_UI_URL: "http://gimmedata.com"}):
        yield


class TestProjectDeploy:
    @pytest.fixture
    def uninitialized_project_dir(self, project_dir):
        Path(project_dir, "prefect.yaml").unlink()
        return project_dir

    @pytest.fixture
    def uninitialized_project_dir_with_git_no_remote(self, uninitialized_project_dir):
        subprocess.run(["git", "init"], cwd=uninitialized_project_dir)
        assert Path(uninitialized_project_dir, ".git").exists()
        return uninitialized_project_dir

    @pytest.fixture
    def uninitialized_project_dir_with_git_with_remote(
        self, uninitialized_project_dir_with_git_no_remote
    ):
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.com/org/repo.git"],
            cwd=uninitialized_project_dir_with_git_no_remote,
        )
        return uninitialized_project_dir_with_git_no_remote

    async def test_project_deploy(self, project_dir, prefect_client: PrefectClient):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar"
            ),
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name",
                "prefect worker start --pool 'test-pool'",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"
        assert deployment.version == "1.0.0"
        assert deployment.tags == ["foo-bar"]
        assert deployment.job_variables == {"env": "prod"}
        assert deployment.enforce_parameter_schema

    async def test_deploy_with_wrapped_flow_decorator(
        self, project_dir, work_pool, prefect_client
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./wrapped-flow-project/flow.py:test_flow -n test-name -p {work_pool.name}"
            ),
            expected_code=0,
            expected_output_does_not_contain=["test-flow"],
            expected_output_contains=[
                "wrapped-flow/test-name",
                f"prefect worker start --pool '{work_pool.name}'",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "wrapped-flow/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == work_pool.name

    async def test_deploy_with_missing_imports(
        self, project_dir, work_pool, prefect_client
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./wrapped-flow-project/missing_imports.py:bloop_flow -n test-name -p {work_pool.name}"
            ),
            expected_code=0,
            expected_output_does_not_contain=["test-flow"],
            expected_output_contains=[
                "wrapped-flow/test-name",
                f"prefect worker start --pool '{work_pool.name}'",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "wrapped-flow/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == work_pool.name

    async def test_project_deploy_with_default_work_pool(
        self, project_dir, prefect_client
    ):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        with temporary_settings(updates={PREFECT_DEFAULT_WORK_POOL_NAME: "test-pool"}):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name --version"
                    " 1.0.0 -v env=prod -t foo-bar"
                ),
                expected_code=0,
                expected_output_contains=[
                    "An important name/test-name",
                    "prefect worker start --pool 'test-pool'",
                ],
            )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"
        assert deployment.version == "1.0.0"
        assert deployment.tags == ["foo-bar"]
        assert deployment.job_variables == {"env": "prod"}
        assert deployment.enforce_parameter_schema

    async def test_project_deploy_with_no_deployment_file(
        self, project_dir, prefect_client: PrefectClient
    ):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar --enforce-parameter-schema"
            ),
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"
        assert deployment.version == "1.0.0"
        assert deployment.tags == ["foo-bar"]
        assert deployment.job_variables == {"env": "prod"}
        assert deployment.enforce_parameter_schema is True

    async def test_project_deploy_with_no_prefect_yaml(self, project_dir, work_pool):
        Path(project_dir, "prefect.yaml").unlink()

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p"
                f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
            ),
            expected_code=0,
            expected_output_contains=[
                "Your Prefect workers will attempt to load your flow from:",
                "To see more options for managing your flow's code, run:",
                "$ prefect init",
            ],
        )

    async def test_deploy_does_not_prompt_storage_when_pull_step_exists(
        self, project_dir, work_pool, interactive_console
    ):
        # write a pull step to the prefect.yaml
        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        config["pull"] = [
            {"prefect.deployments.steps.set_working_directory": {"directory": "."}}
        ]

        with open("prefect.yaml", "w") as f:
            yaml.safe_dump(config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p"
                f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                " --interval 60"
            ),
            user_input=(
                # don't save the deployment configuration
                "n" + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_does_not_contain=[
                "Would you like your workers to pull your flow code from a remote"
                " storage location when running this flow?"
            ],
        )

    @pytest.mark.parametrize(
        "cli_options,expected_limit,expected_strategy",
        [
            pytest.param("-cl 42", 42, None, id="limit-only"),
            pytest.param(
                "-cl 42 --collision-strategy CANCEL_NEW",
                42,
                "CANCEL_NEW",
                id="limit-and-strategy",
            ),
            pytest.param(
                "--collision-strategy CANCEL_NEW",
                None,
                None,
                id="strategy-only",
            ),
        ],
    )
    @pytest.mark.usefixtures("interactive_console", "uninitialized_project_dir")
    async def test_deploy_with_concurrency_limit_and_options(
        self,
        project_dir,
        prefect_client: PrefectClient,
        cli_options,
        expected_limit,
        expected_strategy,
    ):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-deploy-concurrency-limit -p test-pool "
                + "--interval 60 "
                + cli_options
                # "-cl 42 --collision-strategy CANCEL_NEW"
            ),
            expected_code=0,
            user_input=(
                # Decline pulling from remote storage
                "n"
                + readchar.key.ENTER
                +
                # Accept saving the deployment configuration
                "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "prefect deployment run 'An important name/test-deploy-concurrency-limit'"
            ],
        )

        prefect_file = Path("prefect.yaml")
        assert prefect_file.exists()

        with open(prefect_file, "r") as f:
            config = yaml.safe_load(f)

        if expected_limit is not None:
            if expected_strategy is not None:
                assert config["deployments"][0]["concurrency_limit"] == {
                    "limit": expected_limit,
                    "collision_strategy": expected_strategy,
                }
            else:
                assert config["deployments"][0]["concurrency_limit"] == expected_limit
        else:
            assert config["deployments"][0]["concurrency_limit"] is None

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-deploy-concurrency-limit"
        )
        assert deployment.name == "test-deploy-concurrency-limit"
        assert deployment.work_pool_name == "test-pool"

        if expected_limit is not None:
            assert deployment.global_concurrency_limit is not None
            assert deployment.global_concurrency_limit.limit == expected_limit
        else:
            assert deployment.global_concurrency_limit is None

        if expected_strategy is not None:
            assert deployment.concurrency_options is not None
            assert (
                deployment.concurrency_options.collision_strategy == expected_strategy
            )
        else:
            assert deployment.concurrency_options is None

    class TestGeneratedPullAction:
        async def test_project_deploy_generates_pull_action(
            self, work_pool, prefect_client, uninitialized_project_dir
        ):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --interval 60"
                ),
                expected_code=0,
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )
            assert deployment.pull_steps == [
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": str(uninitialized_project_dir)
                    }
                }
            ]

        async def test_project_deploy_with_no_prefect_yaml_git_repo_no_remote(
            self,
            work_pool,
            prefect_client,
            uninitialized_project_dir_with_git_no_remote,
        ):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )
            assert deployment.pull_steps == [
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": str(uninitialized_project_dir_with_git_no_remote)
                    }
                }
            ]

        @pytest.mark.usefixtures("interactive_console")
        async def test_project_deploy_with_no_prefect_yaml_git_repo_user_rejects(
            self,
            work_pool,
            prefect_client,
            uninitialized_project_dir_with_git_with_remote,
        ):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                # User rejects pulling from the remote repo and rejects saving the
                # deployment configuration
                user_input="n" + readchar.key.ENTER + "n" + readchar.key.ENTER,
                expected_code=0,
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )
            assert deployment.pull_steps == [
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": str(uninitialized_project_dir_with_git_with_remote)
                    }
                }
            ]

        @pytest.mark.usefixtures(
            "interactive_console", "uninitialized_project_dir_with_git_with_remote"
        )
        async def test_project_deploy_with_no_prefect_yaml_git_repo(
            self, work_pool, prefect_client
        ):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Accept pulling from remote storage
                    readchar.key.ENTER
                    +
                    # Select remote Git repo as storage (first option)
                    readchar.key.ENTER
                    +
                    # Accept discovered URL
                    readchar.key.ENTER
                    +
                    # Accept discovered branch
                    readchar.key.ENTER
                    +
                    # Choose public repo
                    "n"
                    + readchar.key.ENTER
                    # Accept saving the deployment configuration
                    + "y"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    "Would you like your workers to pull your flow code from a remote"
                    " storage location when running this flow?"
                ],
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )
            assert deployment.pull_steps == [
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://example.com/org/repo.git",
                        "branch": "main",
                    }
                }
            ]

            prefect_file_contents = yaml.safe_load(Path("prefect.yaml").read_text())
            assert prefect_file_contents["pull"] == [
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://example.com/org/repo.git",
                        "branch": "main",
                    }
                }
            ]

        @pytest.mark.usefixtures(
            "interactive_console", "uninitialized_project_dir_with_git_with_remote"
        )
        async def test_project_deploy_with_no_prefect_yaml_git_repo_user_overrides(
            self, work_pool, prefect_client
        ):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Accept pulling from remote storage
                    readchar.key.ENTER
                    +
                    # Select remote Git repo as storage (first option)
                    readchar.key.ENTER
                    +
                    # Reject discovered URL
                    "n"
                    + readchar.key.ENTER
                    +
                    # Enter new URL
                    "https://example.com/org/repo-override.git"
                    + readchar.key.ENTER
                    +
                    # Reject discovered branch
                    "n"
                    + readchar.key.ENTER
                    +
                    # Enter new branch
                    "dev"
                    + readchar.key.ENTER
                    +
                    # Choose public repo
                    "n"
                    + readchar.key.ENTER
                    # Decline saving the deployment configuration
                    + "n"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    "Would you like your workers to pull your flow code from a remote"
                    " storage location when running this flow?"
                ],
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )
            assert deployment.pull_steps == [
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://example.com/org/repo-override.git",
                        "branch": "dev",
                    }
                }
            ]

        @pytest.mark.usefixtures(
            "interactive_console",
            "uninitialized_project_dir_with_git_with_remote",
            "mock_provide_password",
        )
        async def test_project_deploy_with_no_prefect_yaml_git_repo_with_token(
            self,
            work_pool,
            prefect_client,
        ):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Accept pulling from remote storage
                    readchar.key.ENTER
                    +
                    # Select remote Git repo as storage (first option)
                    readchar.key.ENTER
                    +
                    # Accept discovered URL
                    readchar.key.ENTER
                    +
                    # Accept discovered branch
                    readchar.key.ENTER
                    +
                    # Choose private repo
                    "y"
                    + readchar.key.ENTER
                    # Enter token
                    + "my-token"
                    + readchar.key.ENTER
                    # Decline saving the deployment configuration
                    + "n"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    "Would you like your workers to pull your flow code from a remote"
                    " storage location when running this flow?"
                ],
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )
            assert deployment.pull_steps == [
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://example.com/org/repo.git",
                        "branch": "main",
                        "access_token": (
                            "{{ prefect.blocks.secret.deployment-test-name-an-important-name-repo-token }}"
                        ),
                    }
                }
            ]

            token_block = await Secret.load(
                "deployment-test-name-an-important-name-repo-token"
            )
            assert token_block.get() == "my-token"

        @pytest.mark.usefixtures("interactive_console", "uninitialized_project_dir")
        async def test_deploy_with_blob_storage_select_existing_credentials(
            self,
            work_pool,
            prefect_client,
            aws_credentials,
            monkeypatch,
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Accept pulling from remote storage
                    readchar.key.ENTER
                    # Select S3 bucket as storage (second option)
                    + readchar.key.DOWN
                    + readchar.key.ENTER
                    # Provide bucket name
                    + "my-bucket"
                    + readchar.key.ENTER
                    # Accept default folder (root of bucket)
                    + readchar.key.ENTER
                    # Select existing credentials (first option)
                    + readchar.key.ENTER
                    # Decline saving the deployment configuration
                    + "n"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    "Would you like your workers to pull your flow code from a remote"
                    " storage location when running this flow?"
                ],
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )

            assert deployment.pull_steps == [
                {
                    "prefect_aws.deployments.steps.pull_from_s3": {
                        "bucket": "my-bucket",
                        "folder": "",
                        "credentials": (
                            "{{ prefect.blocks.aws-credentials.bezos-creds }}"
                        ),
                    }
                }
            ]

        @pytest.mark.usefixtures("interactive_console", "uninitialized_project_dir")
        async def test_deploy_with_blob_storage_create_credentials(
            self,
            work_pool,
            prefect_client,
            aws_credentials,
            set_ui_url,
            monkeypatch,
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -jv env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Accept pulling from remote storage
                    readchar.key.ENTER
                    # Select S3 bucket as storage (first option)
                    + readchar.key.ENTER
                    # Provide bucket name
                    + "my-bucket"
                    + readchar.key.ENTER
                    # Accept default folder (root of bucket)
                    + readchar.key.ENTER
                    # Create new credentials (second option)
                    + readchar.key.DOWN
                    + readchar.key.ENTER
                    # Enter access key id (only field in this hypothetical)
                    + "my-access-key-id"
                    + readchar.key.ENTER
                    # Accept default name for new credentials block (s3-storage-credentials)
                    + readchar.key.ENTER
                    # Accept saving the deployment configuration
                    + "y"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    (
                        "Would you like your workers to pull your flow code from a"
                        " remote storage location when running this flow?"
                    ),
                    "View/Edit your new credentials block in the UI:",
                    PREFECT_UI_URL.value(),
                ],
            )

            deployment = await prefect_client.read_deployment_by_name(
                "An important name/test-name"
            )

            assert deployment.pull_steps == [
                {
                    "prefect_aws.deployments.steps.pull_from_s3": {
                        "bucket": "my-bucket",
                        "folder": "",
                        "credentials": (
                            "{{ prefect.blocks.aws-credentials.s3-storage-credentials }}"
                        ),
                    }
                }
            ]

        @pytest.mark.usefixtures("interactive_console", "uninitialized_project_dir")
        async def test_build_docker_image_step_auto_build_dockerfile(
            self,
            work_pool,
            prefect_client,
            monkeypatch,
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            prefect_yaml = {
                "build": [
                    {
                        "prefect_docker.deployments.steps.build_docker_image": {
                            "requires": "prefect-docker",
                            "image_name": "repo-name/image-name",
                            "tag": "dev",
                            "dockerfile": "auto",
                        }
                    }
                ]
            }

            with open("prefect.yaml", "w") as f:
                yaml.dump(prefect_yaml, f)

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Decline pulling from remote storage
                    "n"
                    + readchar.key.ENTER
                    +
                    # Accept saving the deployment configuration
                    "y"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    "prefect deployment run 'An important name/test-name'"
                ],
            )

            prefect_file = Path("prefect.yaml")
            assert prefect_file.exists()

            with open(prefect_file, "r") as f:
                config = yaml.safe_load(f)
            dir_name = os.path.basename(os.getcwd())

            assert config["deployments"][0]["pull"] == [
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": f"/opt/prefect/{dir_name}"
                    }
                }
            ]

            mock_step.assert_called_once_with(
                image_name="repo-name/image-name",
                tag="dev",
                dockerfile="auto",
            )
            # check to make sure prefect-docker is not installed
            with pytest.raises(ImportError):
                import prefect_docker  # noqa

        @pytest.mark.usefixtures(
            "interactive_console", "uninitialized_project_dir_with_git_with_remote"
        )
        async def test_build_docker_image_step_custom_dockerfile_remote_flow_code_confirm(
            self,
            work_pool,
            prefect_client,
            monkeypatch,
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            with open("Dockerfile", "w") as f:
                f.write("FROM python:3.9-slim\n")

            prefect_yaml = {
                "build": [
                    {
                        "prefect_docker.deployments.steps.build_docker_image": {
                            "id": "build-image",
                            "requires": "prefect-docker",
                            "image_name": "repo-name/image-name",
                            "tag": "dev",
                            "dockerfile": "Dockerfile",
                        }
                    }
                ]
            }

            with open("prefect.yaml", "w") as f:
                yaml.dump(prefect_yaml, f)

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Accept pulling from remote storage
                    readchar.key.ENTER
                    +
                    # Select remote Git repo as storage (first option)
                    readchar.key.ENTER
                    +
                    # Accept discovered URL
                    readchar.key.ENTER
                    +
                    # Accept discovered branch
                    readchar.key.ENTER
                    +
                    # Choose public repo
                    "n"
                    + readchar.key.ENTER
                    # Accept saving the deployment configuration
                    + "y"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    (
                        "Would you like your workers to pull your flow code from a"
                        " remote storage location when running this flow?"
                    ),
                    "Is this a private repository?",
                    "prefect deployment run 'An important name/test-name'",
                ],
            )

            prefect_file = Path("prefect.yaml")
            assert prefect_file.exists()

            with open(prefect_file, "r") as f:
                config = yaml.safe_load(f)
            assert config["deployments"][0]["pull"] == [
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://example.com/org/repo.git",
                        "branch": "main",
                    }
                }
            ]

            mock_step.assert_called_once_with(
                image_name="repo-name/image-name",
                tag="dev",
                dockerfile="Dockerfile",
            )

            # check to make sure prefect-docker is not installed
            with pytest.raises(ImportError):
                import prefect_docker  # noqa

        @pytest.mark.usefixtures(
            "interactive_console", "uninitialized_project_dir_with_git_with_remote"
        )
        async def test_build_docker_image_step_custom_dockerfile_remote_flow_code_reject(
            self,
            work_pool,
            prefect_client,
            monkeypatch,
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            with open("Dockerfile", "w") as f:
                f.write("FROM python:3.9-slim\n")

            prefect_yaml = {
                "build": [
                    {
                        "prefect_docker.deployments.steps.build_docker_image": {
                            "id": "build-image",
                            "requires": "prefect-docker",
                            "image_name": "repo-name/image-name",
                            "tag": "dev",
                            "dockerfile": "Dockerfile",
                        }
                    }
                ]
            }

            with open("prefect.yaml", "w") as f:
                yaml.dump(prefect_yaml, f)

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Reject pulling from remote git origin
                    "n"
                    + readchar.key.ENTER
                    +
                    # Accept copied flow code into Dockerfile
                    "y"
                    + readchar.key.ENTER
                    +
                    # Provide path to flow code
                    "/opt/prefect/hello-projects/"
                    + readchar.key.ENTER
                    # Accept saving the deployment configuration
                    + "y"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    (
                        "Would you like your workers to pull your flow code from a"
                        " remote storage location when running this flow?"
                    ),
                    (
                        "Does your Dockerfile have a line that copies the current"
                        " working directory"
                    ),
                    "What is the path to your flow code in your Dockerfile?",
                    "prefect deployment run 'An important name/test-name'",
                ],
            )

            prefect_file = Path("prefect.yaml")
            assert prefect_file.exists()

            with open(prefect_file, "r") as f:
                config = yaml.safe_load(f)

            assert config["deployments"][0]["pull"] == [
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": "/opt/prefect/hello-projects/"
                    }
                }
            ]

            mock_step.assert_called_once_with(
                image_name="repo-name/image-name",
                tag="dev",
                dockerfile="Dockerfile",
            )

            # check to make sure prefect-docker is not installed
            with pytest.raises(ImportError):
                import prefect_docker  # noqa

        @pytest.mark.usefixtures(
            "interactive_console", "uninitialized_project_dir_with_git_with_remote"
        )
        async def test_build_docker_image_step_custom_dockerfile_reject_copy_confirm(
            self,
            work_pool,
            prefect_client,
            monkeypatch,
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            with open("Dockerfile", "w") as f:
                f.write("FROM python:3.9-slim\n")
            prefect_yaml = {
                "build": [
                    {
                        "prefect_docker.deployments.steps.build_docker_image": {
                            "id": "build-image",
                            "requires": "prefect-docker",
                            "image_name": "repo-name/image-name",
                            "tag": "dev",
                            "dockerfile": "Dockerfile",
                        }
                    }
                ]
            }

            with open("prefect.yaml", "w") as f:
                yaml.dump(prefect_yaml, f)

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name -p"
                    f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
                    " --interval 60"
                ),
                expected_code=1,
                user_input=(
                    # Reject pulling from remote git origin
                    "n"
                    + readchar.key.ENTER
                    +
                    # Reject copied flow code into Dockerfile
                    "n"
                ),
                expected_output_contains=[
                    (
                        "Would you like your workers to pull your flow code from a"
                        " remote storage location when running this flow?"
                    ),
                    (
                        "Does your Dockerfile have a line that copies the current"
                        " working directory"
                    ),
                    (
                        "Your flow code must be copied into your Docker image"
                        " to run your deployment."
                    ),
                ],
            )

            # check to make sure prefect-docker is not installed
            with pytest.raises(ImportError):
                import prefect_docker  # noqa

    class TestGeneratedPushAction:
        @pytest.mark.usefixtures(
            "interactive_console", "uninitialized_project_dir_with_git_with_remote"
        )
        async def test_deploy_select_blob_storage_configures_push_step(
            self,
            work_pool,
            prefect_client,
            aws_credentials,
            monkeypatch,
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name"
                    f" -p {work_pool.name} --interval 60"
                ),
                expected_code=0,
                user_input=(
                    # Accept pulling from remote storage
                    "y"
                    + readchar.key.ENTER
                    # Select S3 bucket as storage (second option)
                    + readchar.key.DOWN
                    + readchar.key.ENTER
                    # Provide bucket name
                    + "my-bucket"
                    + readchar.key.ENTER
                    # Accept default folder (root of bucket)
                    + readchar.key.ENTER
                    # Select existing credentials (first option)
                    + readchar.key.ENTER
                    # Accept saving the deployment configuration
                    + "y"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    "Would you like your workers to pull your flow code from a remote"
                    " storage location when running this flow?"
                ],
            )

            mock_step.assert_called_once_with(
                bucket="my-bucket",
                folder="",
                credentials={"aws_access_key_id": "AKIA1234"},
            )

            prefect_file = Path("prefect.yaml")
            assert prefect_file.exists()

            with open(prefect_file, "r") as f:
                config = yaml.safe_load(f)

            assert config["push"] == [
                {
                    "prefect_aws.deployments.steps.push_to_s3": {
                        "bucket": "my-bucket",
                        "folder": "",
                        "credentials": (
                            "{{ prefect.blocks.aws-credentials.bezos-creds }}"
                        ),
                    }
                }
            ]

            assert config["pull"] == [
                {
                    "prefect_aws.deployments.steps.pull_from_s3": {
                        "bucket": "my-bucket",
                        "folder": "",
                        "credentials": (
                            "{{ prefect.blocks.aws-credentials.bezos-creds }}"
                        ),
                    }
                }
            ]

    async def test_project_deploy_with_empty_dep_file(
        self, project_dir, prefect_client, work_pool
    ):
        deployment_file = project_dir / "deployment.yaml"
        with deployment_file.open(mode="w") as f:
            f.write("{}")

        deployment_name = f"test-name-{uuid4()}"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n {deployment_name} -p {work_pool.name}",
            expected_code=0,
            expected_output_contains=["An important name/test"],
        )
        deployment = await prefect_client.read_deployment_by_name(
            f"An important name/{deployment_name}"
        )
        assert deployment.name == deployment_name
        assert deployment.work_pool_name == work_pool.name

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_templates_values(self, work_pool, prefect_client):
        # prepare a templated deployment
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"][0]["name"] = "test-name"
        contents["deployments"][0]["version"] = "{{ input }}"
        contents["deployments"][0]["tags"] = "{{ output2 }}"
        contents["deployments"][0]["description"] = "{{ output1 }}"

        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # update prefect.yaml to include a new build step
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        # test step that returns a dictionary of inputs and output1, output2
        prefect_config["build"] = [
            {"prefect.testing.utilities.a_test_step": {"input": "foo"}}
        ]

        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        deployment_name = f"test-name-{uuid4()}"
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n {deployment_name} -p {work_pool.name}",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            f"An important name/{deployment_name}"
        )
        assert deployment.name == deployment_name
        assert deployment.work_pool_name == work_pool.name
        assert deployment.version == "foo"
        assert deployment.tags == ["b", "2", "3"]
        assert deployment.description == "1"

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_templates_env_var_values(
        self, prefect_client, work_pool, monkeypatch
    ):
        # prepare a templated deployment
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        deployment_name = f"test-name-{uuid4()}"
        contents["deployments"][0]["name"] = deployment_name
        contents["deployments"][0]["version"] = "{{ $MY_VERSION }}"
        contents["deployments"][0]["tags"] = "{{ $MY_TAGS }}"
        contents["deployments"][0]["description"] = "{{ $MY_DESCRIPTION }}"

        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # update prefect.yaml to include some new build steps
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        monkeypatch.setenv("MY_DIRECTORY", "bar")
        monkeypatch.setenv("MY_FILE", "foo.txt")

        prefect_config["build"] = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "id": "get-dir",
                    "script": "echo '{{ $MY_DIRECTORY }}'",
                    "stream_output": True,
                }
            },
        ]

        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        monkeypatch.setenv("MY_VERSION", "foo")
        monkeypatch.setenv("MY_TAGS", "b,2,3")
        monkeypatch.setenv("MY_DESCRIPTION", "1")

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n {deployment_name} -p {work_pool.name}",
            expected_output_contains=["bar"],
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            f"An important name/{deployment_name}"
        )

        assert deployment.name == deployment_name
        assert deployment.work_pool_name == work_pool.name
        assert deployment.version == "foo"
        assert deployment.tags == ["b", ",", "2", ",", "3"]
        assert deployment.description == "1"

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_with_default_parameters(
        self, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["parameters"] = {
            "number": 1,
            "message": "hello",
        }
        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["entrypoint"] = "flows/hello.py:my_flow"
        deploy_config["deployments"][0]["work_pool"]["name"] = work_pool.name

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.parameters == {"number": 1, "message": "hello"}

    @pytest.mark.parametrize(
        "option", ["--param number=2", "--params '{\"number\": 2}'"]
    )
    async def test_project_deploy_with_default_parameters_from_cli(
        self, project_dir, prefect_client, work_pool, option
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        config["deployments"][0]["parameters"] = {
            "number": 1,
            "message": "hello",
        }
        config["deployments"][0]["name"] = "test-name"
        config["deployments"][0]["entrypoint"] = "flows/hello.py:my_flow"
        config["deployments"][0]["work_pool"]["name"] = work_pool.name

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy -n test-name {option}",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.parameters == {"number": 2, "message": "hello"}

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_templates_pull_step_safely(
        self, prefect_client, work_pool
    ):
        """
        We want step outputs to get templated, but block references to only be
        retrieved at runtime.

        Unresolved placeholders should be left as-is, and not be resolved
        to allow templating between steps in the pull action.
        """

        await Secret(value="super-secret-name").save(name="test-secret")

        # update prefect.yaml to include a new build step
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        # test step that returns a dictionary of inputs and output1, output2
        prefect_config["build"] = [
            {"prefect.testing.utilities.a_test_step": {"input": "foo"}}
        ]

        prefect_config["pull"] = [
            {
                "prefect.testing.utilities.b_test_step": {
                    "id": "b-test-step",
                    "input": "{{ output1 }}",
                    "secret-input": "{{ prefect.blocks.secret.test-secret }}",
                },
            },
            {
                "prefect.testing.utilities.b_test_step": {
                    "input": "foo-{{ b-test-step.output1 }}",
                    "secret-input": "{{ b-test-step.output1 }}",
                },
            },
        ]
        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name -p {work_pool.name}",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.pull_steps == [
            {
                "prefect.testing.utilities.b_test_step": {
                    "id": "b-test-step",
                    "input": 1,
                    "secret-input": "{{ prefect.blocks.secret.test-secret }}",
                }
            },
            {
                "prefect.testing.utilities.b_test_step": {
                    "input": "foo-{{ b-test-step.output1 }}",
                    "secret-input": "{{ b-test-step.output1 }}",
                }
            },
        ]

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_templates_pull_step_in_deployments_section_safely(
        self, prefect_client, work_pool
    ):
        """
        We want step outputs to get templated, but block references to only be
        retrieved at runtime.

        Unresolved placeholders should be left as-is, and not be resolved
        to allow templating between steps in the pull action.
        """

        await Secret(value="super-secret-name").save(name="test-secret")

        # update prefect.yaml to include a new build step
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        # test step that returns a dictionary of inputs and output1, output2
        prefect_config["build"] = [
            {"prefect.testing.utilities.a_test_step": {"input": "foo"}}
        ]

        prefect_config["deployments"][0]["pull"] = [
            {
                "prefect.testing.utilities.b_test_step": {
                    "id": "b-test-step",
                    "input": "{{ output1 }}",
                    "secret-input": "{{ prefect.blocks.secret.test-secret }}",
                },
            },
            {
                "prefect.testing.utilities.b_test_step": {
                    "input": "foo-{{ b-test-step.output1 }}",
                    "secret-input": "{{ b-test-step.output1 }}",
                },
            },
        ]
        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name -p {work_pool.name}",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.pull_steps == [
            {
                "prefect.testing.utilities.b_test_step": {
                    "id": "b-test-step",
                    "input": 1,
                    "secret-input": "{{ prefect.blocks.secret.test-secret }}",
                }
            },
            {
                "prefect.testing.utilities.b_test_step": {
                    "input": "foo-{{ b-test-step.output1 }}",
                    "secret-input": "{{ b-test-step.output1 }}",
                }
            },
        ]

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_reads_entrypoint_from_prefect_yaml(self, work_pool):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["entrypoint"] = "flows/hello.py:my_flow"
        deploy_config["deployments"][0]["work_pool"]["name"] = work_pool.name

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_exits_with_no_entrypoint_configured(self, work_pool):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["work_pool"]["name"] = work_pool.name

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name",
            expected_code=1,
            expected_output_contains="An entrypoint must be provided:",
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_without_name_interactive(self, work_pool, prefect_client):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -p {work_pool.name} --interval 3600"
            ),
            expected_code=0,
            user_input=(
                # Provide a deployment name
                "test-prompt-name"
                + readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # Decline saving the deployment configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Deployment name",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-prompt-name"
        )
        assert deployment.name == "test-prompt-name"
        assert deployment.work_pool_name == work_pool.name
        assert deployment.entrypoint == "./flows/hello.py:my_flow"

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_without_work_pool_non_interactive(self):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name",
            expected_code=1,
            expected_output_contains=[
                "A work pool is required to deploy this flow. Please specify a"
                " work pool name via the '--pool' flag or in your prefect.yaml file."
            ],
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_without_work_pool_interactive(
        self, work_pool, prefect_client
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name --interval 3600",
            expected_code=0,
            user_input=(
                # Select only existing work pool
                readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # Decline saving the deployment configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Which work pool would you like to deploy this flow to?",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == work_pool.name
        assert deployment.entrypoint == "./flows/hello.py:my_flow"

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_with_prefect_agent_work_pool_non_interactive(
        self, default_agent_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p"
                f" {default_agent_pool.name}"
            ),
            expected_code=1,
            expected_output_contains=(
                "Cannot create a project-style deployment with work pool of type"
                " 'prefect-agent'. If you wish to use an agent with your deployment,"
                " please use the `prefect deployment build` command."
            ),
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_with_prefect_agent_work_pool_interactive(
        self, work_pool, prefect_client, default_agent_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p"
                f" {default_agent_pool.name} --interval 3600"
            ),
            expected_code=0,
            user_input=(
                # Accept only existing work pool
                readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # Decline saving the deployment configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                (
                    "You've chosen a work pool with type 'prefect-agent' which cannot"
                    " be used for project-style deployments. Let's pick another work"
                    " pool to deploy to."
                ),
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == work_pool.name
        assert deployment.entrypoint == "./flows/hello.py:my_flow"

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_with_push_pool_no_worker_start_message(self, push_work_pool):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p"
                f" {push_work_pool.name} --interval 3600"
            ),
            expected_code=0,
            user_input=(
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                # Decline saving the deployment configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_does_not_contain=[
                f"$ prefect worker start --pool {push_work_pool.name!r}",
            ],
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_with_no_available_work_pool_interactive(self, prefect_client):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name --interval 3600",
            expected_code=0,
            user_input=(
                # Accept creating a new work pool
                readchar.key.ENTER
                # Select the first work pool type
                + readchar.key.ENTER
                # Enter a name for the new work pool
                + "test-created-via-deploy"
                + readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # Decline save the deployment configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                (
                    "Looks like you don't have any work pools this flow can be deployed"
                    " to. Would you like to create one?"
                ),
                (
                    "What infrastructure type would you like to use for your new work"
                    " pool?"
                ),
                "Work pool name",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-created-via-deploy"
        assert deployment.entrypoint == "./flows/hello.py:my_flow"

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_with_entrypoint_does_not_fail_with_missing_prefect_folder(
        self, work_pool
    ):
        Path(".prefect").rmdir()
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name -p {work_pool.name}",
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/test-name' successfully created"
            ],
        )

    @pytest.mark.parametrize("schedule_value", [None, {}])
    @pytest.mark.usefixtures("project_dir", "interactive_console")
    async def test_deploy_does_not_prompt_schedule_when_empty_schedule_prefect_yaml(
        self, schedule_value, work_pool, prefect_client
    ):
        prefect_yaml_file = Path("prefect.yaml")
        with prefect_yaml_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"] = [
            {
                "name": "test-name",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {
                    "name": work_pool.name,
                },
                "schedule": schedule_value,
            }
        ]

        with prefect_yaml_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name",
            user_input=(
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                # reject saving configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert len(deployment.schedules) == 0

    @pytest.mark.parametrize("build_value", [None, {}])
    @pytest.mark.usefixtures("project_dir", "interactive_console")
    async def test_deploy_does_not_prompt_build_docker_image_when_empty_build_action_prefect_yaml(
        self, build_value, work_pool, prefect_client
    ):
        prefect_yaml_file = Path("prefect.yaml")
        with prefect_yaml_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"] = [
            {
                "name": "test-name",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {
                    "name": work_pool.name,
                },
                "build": build_value,
                "schedule": {},
            }
        ]

        with prefect_yaml_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name",
            user_input=(
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                # reject saving configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_does_not_contain="Would you like to build a Docker image?",
        )

        assert await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

    async def test_deploy_with_bad_run_shell_script_raises(
        self, project_dir, work_pool
    ):
        """
        Regression test for a bug where deployment steps would continue even when
        a `run_shell_script` step failed.
        """
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        config["build"] = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "id": "test",
                    "script": "cat nothing",
                    "stream_output": True,
                }
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(config, f)

        with pytest.raises(StepExecutionError):
            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name --pool"
                    f" {work_pool.name}"
                ),
            )

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_templates_env_vars(
        self, prefect_client, monkeypatch, work_pool
    ):
        # set up environment variables
        monkeypatch.setenv("WORK_POOL", work_pool.name)
        monkeypatch.setenv("MY_VAR", "my-value")

        # set up prefect.yaml that has env var placeholders for the work pool name
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        prefect_config["deployments"] = [
            {
                "name": "test-deployment",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {"name": "{{ $WORK_POOL }}"},
            },
            {
                "name": "test-deployment2",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {"name": "{{ $WORK_POOL }}"},
            },
        ]
        prefect_config["build"] = [
            {"prefect.testing.utilities.a_test_step": {"input": "{{ $MY_VAR }}"}}
        ]

        # save config to prefect.yaml
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            expected_output_does_not_contain=(
                "This deployment configuration references work pool",
                (
                    "This means no worker will be able to pick up its runs. You can"
                    " create a work pool in the Prefect UI."
                ),
            ),
        )
        assert result.exit_code == 0

        deployments = await prefect_client.read_deployments()

        assert len(deployments) == 2

        assert deployments[0].name == "test-deployment"
        assert deployments[0].work_pool_name == work_pool.name

        assert deployments[1].name == "test-deployment2"
        assert deployments[1].work_pool_name == work_pool.name

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert (
            config["build"][0]["prefect.testing.utilities.a_test_step"]["input"]
            == "{{ $MY_VAR }}"
        )

        assert config["deployments"][0]["work_pool"]["name"] == "{{ $WORK_POOL }}"

        assert config["deployments"][1]["work_pool"]["name"] == "{{ $WORK_POOL }}"

    @pytest.mark.usefixtures("interactive_console")
    class TestRemoteStoragePicklist:
        @pytest.mark.usefixtures("uninitialized_project_dir_with_git_no_remote")
        async def test_no_git_option_when_no_remote_url(
            self, docker_work_pool, aws_credentials, monkeypatch
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name --cron '0 4 * * *' -p"
                    " test-docker-work-pool"
                ),
                expected_code=0,
                expected_output_contains="s3",
                expected_output_does_not_contain="Git Repo",
                user_input=(
                    # no custom image
                    "n"
                    + readchar.key.ENTER
                    # Accept remote storage
                    + "y"
                    + readchar.key.ENTER
                    # Select S3
                    + readchar.key.ENTER
                    # Enter bucket name
                    + "test-bucket"
                    + readchar.key.ENTER
                    # Enter bucket prefix
                    + readchar.key.ENTER
                    # Select existing credentials
                    + readchar.key.ENTER
                    # Decline saving the deployment configuration
                    + "n"
                    + readchar.key.ENTER
                ),
            )

        @pytest.mark.usefixtures("uninitialized_project_dir_with_git_with_remote")
        async def test_git_option_present_when_remote_url(
            self, docker_work_pool, monkeypatch
        ):
            mock_step = mock.MagicMock()
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_object", lambda x: mock_step
            )
            monkeypatch.setattr(
                "prefect.deployments.steps.core.import_module",
                lambda x: None,
            )

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=(
                    "deploy ./flows/hello.py:my_flow -n test-name --cron '0 4 * * *' -p"
                    " test-docker-work-pool"
                ),
                expected_code=0,
                expected_output_contains="Git Repo",
                expected_output_does_not_contain="s3",
                user_input=(
                    # no custom image
                    "n"
                    + readchar.key.ENTER
                    # Accept remote storage
                    + "y"
                    + readchar.key.ENTER
                    # Select Git (first option)
                    + readchar.key.ENTER
                    # Confirm git url
                    + readchar.key.ENTER
                    # Confirm git branch
                    + readchar.key.ENTER
                    # Not a private repo
                    + "n"
                    + readchar.key.ENTER
                    # Decline saving the deployment configuration
                    + "n"
                    + readchar.key.ENTER
                ),
            )


class TestSchedules:
    @pytest.mark.usefixtures("project_dir")
    async def test_passing_cron_schedules_to_deploy(self, work_pool, prefect_client):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --cron '0 4 * * *'"
                f" --timezone 'Europe/Berlin' --pool {work_pool.name}"
            ),
        )
        assert result.exit_code == 0

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        schedule = deployment.schedules[0].schedule
        assert schedule.cron == "0 4 * * *"
        assert schedule.timezone == "Europe/Berlin"

    @pytest.mark.usefixtures("project_dir")
    async def test_deployment_yaml_cron_schedule(self, work_pool, prefect_client):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["schedule"]["cron"] = "0 4 * * *"
        deploy_config["deployments"][0]["schedule"]["timezone"] = "America/Chicago"

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
        )
        assert result.exit_code == 0

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        schedule = deployment.schedules[0].schedule
        assert schedule.cron == "0 4 * * *"
        assert schedule.timezone == "America/Chicago"

    @pytest.mark.usefixtures("project_dir")
    async def test_deployment_yaml_cron_schedule_timezone_cli(
        self, work_pool, prefect_client
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["schedule"]["cron"] = "0 4 * * *"
        deploy_config["deployments"][0]["schedule"]["timezone"] = "America/Chicago"

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name "
                f"--timezone 'Europe/Berlin' --pool {work_pool.name}"
            ),
        )
        assert result.exit_code == 0

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert len(deployment.schedules) == 1
        schedule = deployment.schedules[0].schedule
        assert schedule.cron == "0 4 * * *"
        assert schedule.timezone == "Europe/Berlin"

    @pytest.mark.usefixtures("project_dir")
    async def test_passing_interval_schedules_to_deploy(
        self, work_pool, prefect_client
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 42"
                " --anchor-date 2040-02-02 --timezone 'America/New_York' --pool"
                f" {work_pool.name}"
            ),
        )
        assert result.exit_code == 0

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert len(deployment.schedules) == 1
        schedule = deployment.schedules[0].schedule
        assert schedule.interval == timedelta(seconds=42)
        assert schedule.anchor_date == pendulum.parse("2040-02-02")
        assert schedule.timezone == "America/New_York"

    @pytest.mark.usefixtures("project_dir")
    async def test_interval_schedule_deployment_yaml(self, prefect_client, work_pool):
        prefect_yaml = Path("prefect.yaml")
        with prefect_yaml.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["schedule"]["interval"] = 42
        deploy_config["deployments"][0]["schedule"]["anchor_date"] = "2040-02-02"
        deploy_config["deployments"][0]["schedule"]["timezone"] = "America/Chicago"

        with prefect_yaml.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
        )
        assert result.exit_code == 0

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert len(deployment.schedules) == 1
        schedule = deployment.schedules[0].schedule
        assert schedule.interval == timedelta(seconds=42)
        assert schedule.anchor_date == pendulum.parse("2040-02-02")
        assert schedule.timezone == "America/Chicago"

    @pytest.mark.usefixtures("project_dir")
    async def test_parsing_rrule_schedule_string_literal(
        self, prefect_client, work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --rrule"
                " 'DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17'"
                f" --pool {work_pool.name}"
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        schedule = deployment.schedules[0].schedule
        assert (
            schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )

    @pytest.mark.usefixtures("project_dir")
    async def test_rrule_deployment_yaml(self, work_pool, prefect_client):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["schedule"][
            "rrule"
        ] = "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --rrule"
                " 'DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17'"
                f" --pool {work_pool.name}"
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        schedule = deployment.schedules[0].schedule
        assert (
            schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )

    @pytest.mark.usefixtures("project_dir")
    async def test_can_provide_multiple_schedules_via_command(
        self, prefect_client, work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name --cron '* * * * *' --interval 42 --rrule 'FREQ=HOURLY' --pool {work_pool.name}",
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/test-name' successfully created"
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        schedule_config = {}
        for deployment_schedule in deployment.schedules:
            schedule = deployment_schedule.schedule
            if isinstance(schedule, IntervalSchedule):
                schedule_config["interval"] = schedule.interval
            elif isinstance(schedule, CronSchedule):
                schedule_config["cron"] = schedule.cron
            elif isinstance(schedule, RRuleSchedule):
                schedule_config["rrule"] = schedule.rrule
            else:
                raise AssertionError("Unknown schedule type received")

        assert schedule_config == {
            "interval": timedelta(seconds=42),
            "cron": "* * * * *",
            "rrule": "FREQ=HOURLY",
        }

    @pytest.mark.usefixtures("project_dir")
    async def test_can_provide_multiple_schedules_via_yaml(
        self, prefect_client, work_pool
    ):
        prefect_yaml = Path("prefect.yaml")
        with prefect_yaml.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["schedules"] = [
            {"interval": 42},
            {"cron": "* * * * *"},
            {"rrule": "FREQ=HOURLY"},
        ]

        with prefect_yaml.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}",
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/test-name' successfully created"
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        schedule_config = {}
        for deployment_schedule in deployment.schedules:
            schedule = deployment_schedule.schedule
            if isinstance(schedule, IntervalSchedule):
                schedule_config["interval"] = schedule.interval
            elif isinstance(schedule, CronSchedule):
                schedule_config["cron"] = schedule.cron
            elif isinstance(schedule, RRuleSchedule):
                schedule_config["rrule"] = schedule.rrule
            else:
                raise AssertionError("Unknown schedule type received")

        assert schedule_config == {
            "interval": timedelta(seconds=42),
            "cron": "* * * * *",
            "rrule": "FREQ=HOURLY",
        }

    @pytest.mark.usefixtures("project_dir")
    async def test_yaml_with_schedule_and_schedules_raises_error(self, work_pool):
        prefect_yaml = Path("prefect.yaml")
        with prefect_yaml.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["schedule"]["interval"] = 42
        deploy_config["deployments"][0]["schedules"] = [{"interval": 42}]

        with prefect_yaml.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            expected_code=1,
            expected_output_contains="Both 'schedule' and 'schedules' keys are present in the deployment configuration. Please use only use `schedules`.",
        )

    @pytest.mark.usefixtures("project_dir")
    async def test_yaml_with_schedule_prints_deprecation_warning(self, work_pool):
        prefect_yaml = Path("prefect.yaml")
        with prefect_yaml.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["schedule"]["interval"] = 42

        with prefect_yaml.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            expected_code=0,
            expected_output_contains="Defining a schedule via the `schedule` key in the deployment",
        )

    @pytest.mark.usefixtures("project_dir")
    async def test_can_provide_multiple_schedules_of_the_same_type_via_command(
        self, prefect_client, work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name --cron '* * * * *' --cron '0 * * * *' --pool {work_pool.name}",
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/test-name' successfully created"
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        schedules = set()
        for deployment_schedule in deployment.schedules:
            schedule = deployment_schedule.schedule
            assert isinstance(schedule, CronSchedule)
            schedules.add(schedule.cron)

        assert schedules == {
            "* * * * *",
            "0 * * * *",
        }

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_interval_schedule_interactive(
        self, prefect_client, work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            user_input=(
                # Confirm schedule creation
                readchar.key.ENTER
                # Select interval schedule
                + readchar.key.ENTER
                # Enter invalid interval
                + "bad interval"
                + readchar.key.ENTER
                # Enter another invalid interval
                + "0"
                + readchar.key.ENTER
                # Enter valid interval
                + "42"
                + readchar.key.ENTER
                # accept schedule being active
                + readchar.key.ENTER
                # decline adding another schedule
                + readchar.key.ENTER
                # decline save
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "? Seconds between scheduled runs",
                "Please enter a valid interval denoted in seconds",
                "Interval must be greater than 0",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedules[0].schedule.interval == timedelta(seconds=42)

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_default_interval_schedule_interactive(
        self, prefect_client, work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            user_input=(
                # Confirm schedule creation
                readchar.key.ENTER
                # Select interval schedule
                + readchar.key.ENTER
                # Enter default interval
                + readchar.key.ENTER
                # accept schedule being active
                + readchar.key.ENTER
                # decline adding another schedule
                + readchar.key.ENTER
                # decline save
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Seconds between scheduled runs (3600)",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedules[0].schedule.interval == timedelta(seconds=3600)

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_cron_schedule_interactive(self, prefect_client, work_pool):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            user_input=(
                # Confirm schedule creation
                readchar.key.ENTER
                # Select cron schedule
                + readchar.key.DOWN
                + readchar.key.ENTER
                # Enter invalid cron string
                + "bad cron string"
                + readchar.key.ENTER
                # Enter cron
                + "* * * * *"
                + readchar.key.ENTER
                # Enter invalid timezone
                + "bad timezone"
                + readchar.key.ENTER
                # Select default timezone
                + readchar.key.ENTER
                # accept schedule being active
                + readchar.key.ENTER
                # decline adding another schedule
                + readchar.key.ENTER
                # decline save
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "? Cron string",
                "Please enter a valid cron string",
                "? Timezone",
                "Please enter a valid timezone",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedules[0].schedule.cron == "* * * * *"

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_rrule_schedule_interactive(self, prefect_client, work_pool):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            user_input=(
                # Confirm schedule creation
                readchar.key.ENTER
                # Select rrule schedule
                + readchar.key.DOWN
                + readchar.key.DOWN
                + readchar.key.ENTER
                # Enter invalid rrule string
                + "bad rrule string"
                + readchar.key.ENTER
                # Enter valid rrule string
                + "FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=20240730T040000Z"
                + readchar.key.ENTER
                # Enter invalid timezone
                + "bad timezone"
                + readchar.key.ENTER
                # Select default timezone
                + readchar.key.ENTER
                # accept schedule being active
                + readchar.key.ENTER
                # decline adding another schedule
                + readchar.key.ENTER
                # decline save
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert (
            deployment.schedules[0].schedule.rrule
            == "FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=20240730T040000Z"
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_no_schedule_interactive(self, prefect_client, work_pool):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            user_input=(
                # Decline schedule creation
                "n"
                + readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # Decline save
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert len(deployment.schedules) == 0

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_with_inactive_schedule(self, work_pool, prefect_client):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["schedule"]["cron"] = "0 4 * * *"
        deploy_config["deployments"][0]["schedule"]["timezone"] = "America/Chicago"
        deploy_config["deployments"][0]["schedule"]["active"] = False

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
        )
        assert result.exit_code == 0

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        deployment_schedule = deployment.schedules[0]
        assert deployment_schedule.active is False
        assert deployment_schedule.schedule.cron == "0 4 * * *"
        assert deployment_schedule.schedule.timezone == "America/Chicago"

    @pytest.mark.usefixtures("project_dir", "enable_schedule_concurrency")
    async def test_deploy_with_max_active_runs_and_catchup_provided_for_schedule(
        self, work_pool, prefect_client
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"] = [
            {
                "name": "test-name",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
                "schedules": [
                    {
                        "interval": 42,
                        "max_active_runs": 5,
                        "catchup": True,
                    }
                ],
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        assert deployment.schedules[0].max_active_runs == 5
        assert deployment.schedules[0].catchup is True

    @pytest.mark.usefixtures(
        "project_dir", "interactive_console", "enable_schedule_concurrency"
    )
    async def test_deploy_with_max_active_runs_and_catchup_interactive(
        self, work_pool, prefect_client
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -n test-name --pool {work_pool.name}"
            ),
            user_input=(
                # Confirm schedule creation
                readchar.key.ENTER
                # Select interval schedule
                + readchar.key.ENTER
                # Enter interval
                + "42"
                + readchar.key.ENTER
                # accept schedule being active
                + readchar.key.ENTER
                # Enter max active runs
                + "5"
                + readchar.key.ENTER
                # Enter catchup
                + "y"
                + readchar.key.ENTER
                # decline adding another schedule
                + readchar.key.ENTER
                # decline save
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        assert deployment.schedules[0].max_active_runs == 5
        assert deployment.schedules[0].catchup is True

    @pytest.mark.usefixtures("project_dir")
    async def test_yaml_null_schedules(self, prefect_client, work_pool):
        prefect_yaml_content = f"""
        deployments:
          - name: test-name
            entrypoint: flows/hello.py:my_flow
            work_pool:
              name: {work_pool.name}
            schedules: null
        """

        with open("prefect.yaml", "w") as f:
            f.write(prefect_yaml_content)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        assert deployment.schedules == []


class TestMultiDeploy:
    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_all(self, prefect_client, work_pool):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        # Create multiple deployments
        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-2",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)
        # Deploy all
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name-1",
                "An important name/test-name-2",
            ],
            expected_output_does_not_contain=[
                "You have passed options to the deploy command, but you are"
                " creating or updating multiple deployments. These options"
                " will be ignored."
            ],
        )

        # Check if deployments were created correctly
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name
        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_all_schedules_remain_inactive(
        self, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "schedule": {"interval": 60.0, "active": True},
                "work_pool": {"name": work_pool.name},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-2",
                "schedule": {"interval": 60.0, "active": False},
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name-1",
                "An important name/test-name-2",
            ],
            expected_output_does_not_contain=[
                "You have passed options to the deploy command, but you are"
                " creating or updating multiple deployments. These options"
                " will be ignored."
            ],
        )

        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

        assert deployment1.name == "test-name-1"
        assert deployment1.schedules[0].active is True
        assert deployment2.name == "test-name-2"
        assert deployment2.schedules[0].active is False

    async def test_deploy_selected_deployments(
        self, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
                "enforce_parameter_schema": True,
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-2",
                "work_pool": {"name": work_pool.name},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-3",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy only two deployments by name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --name test-name-1 --name test-name-2",
            expected_code=0,
            expected_output_contains=[
                (
                    "Deployment 'An important name/test-name-1' successfully created"
                    " with id"
                ),
                (
                    "Deployment 'An important name/test-name-2' successfully created"
                    " with id"
                ),
            ],
            expected_output_does_not_contain=[
                (
                    "Deployment 'An important name/test-name-3' successfully created"
                    " with id"
                ),
                (
                    "You have passed options to the deploy command, but you are"
                    " creating or updating multiple deployments. These options"
                    " will be ignored."
                ),
            ],
        )

        # Check if the two deployments were created correctly
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name
        assert deployment1.enforce_parameter_schema is True
        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name
        assert deployment2.enforce_parameter_schema

        # Check if the third deployment was not created
        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-3"
            )

    async def test_deploy_single_with_cron_schedule(
        self, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        # Create multiple deployments
        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-2",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)
        # Deploy a single deployment with a cron schedule
        cron_schedule = "0 * * * *"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy --name test-name-1 --cron '{cron_schedule}'",
            expected_code=0,
            expected_output_contains=[
                (
                    "Deployment 'An important name/test-name-1' successfully created"
                    " with id"
                ),
            ],
        )

        # Check if the deployment was created correctly
        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )

        assert deployment.name == "test-name-1"
        assert deployment.work_pool_name == work_pool.name
        assert len(deployment.schedules) == 1
        assert deployment.schedules[0].schedule == CronSchedule(cron="0 * * * *")

        # Check if the second deployment was not created
        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-2"
            )

    @pytest.mark.parametrize(
        "deployment_selector_options", ["--all", "-n test-name-1 -n test-name-2"]
    )
    async def test_deploy_multiple_with_cli_options(
        self, project_dir, prefect_client, work_pool, deployment_selector_options
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        # Create multiple deployments
        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-2",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy multiple deployments with CLI options
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy {deployment_selector_options} --cron '0 * * * *'",
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name-1",
                "An important name/test-name-2",
                (
                    "You have passed options to the deploy command, but you are"
                    " creating or updating multiple deployments. These options will be"
                    " ignored."
                ),
            ],
        )

        # Check if deployments were created correctly and without the provided CLI options
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name
        assert len(deployment1.schedules) == 0

        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name
        assert len(deployment2.schedules) == 0

    async def test_deploy_with_cli_option_name(
        self, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy --name from-cli-name --pool"
                f" {work_pool.name} ./flows/hello.py:my_flow"
            ),
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/from-cli-name' successfully created"
                " with id"
            ],
        )

        # Check name from deployment.yaml was not used
        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-1"
            )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/from-cli-name"
        )
        deployment.name = "from-cli-name"

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_without_name_in_prefect_yaml(self, prefect_client, work_pool):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        # Create multiple deployments
        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                # Missing name
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Attempt to deploy all
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            expected_output_contains=["Discovered unnamed deployment. Skipping..."],
        )

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-2"
            )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_without_name_in_prefect_yaml_interactive(
        self, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        # Create multiple deployments
        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                # Missing name
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Attempt to deploy all
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            user_input=(
                # reject saving configuration
                "n"
                + readchar.key.ENTER
                # accept naming deployment
                + "y"
                + readchar.key.ENTER
                # enter deployment name
                + "test-name-2"
                + readchar.key.ENTER
                # decline remote storage
                + "n"
                + readchar.key.ENTER
                # reject saving configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Discovered unnamed deployment.",
                "Would you like to give this deployment a name and deploy it?",
                "Deployment name",
            ],
        )

        assert await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_without_name_in_prefect_yaml_interactive_user_skips(
        self, prefect_client: PrefectClient, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        # Create multiple deployments
        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                # Missing name
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Attempt to deploy all
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            user_input=(
                # decline remote storage
                "n"
                + readchar.key.ENTER
                # reject saving configuration
                + "n"
                + readchar.key.ENTER
                # reject naming deployment
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Discovered unnamed deployment.",
                "Would you like to give this deployment a name and deploy it?",
                "Skipping unnamed deployment.",
            ],
        )

        assert len(await prefect_client.read_deployments()) == 1

    async def test_deploy_with_name_not_in_prefect_yaml(
        self, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-2",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Attempt to deploy all
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name-2 -n test-name-3",
            expected_code=0,
            expected_output_contains=[
                (
                    "The following deployment(s) could not be found and will not be"
                    " deployed: test-name-3"
                ),
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )
        assert deployment.name == "test-name-2"
        assert deployment.work_pool_name == work_pool.name

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-3"
            )

    async def test_deploy_with_single_deployment_with_name_in_file(
        self, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "name": "test-name-1",
                "work_pool": {"name": work_pool.name},
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)
        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name-1",
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name-1",
            ],
        )

        # Check if the deployment was created correctly
        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment.name == "test-name-1"
        assert deployment.work_pool_name == work_pool.name

    async def test_deploy_errors_with_empty_deployments_list_and_no_cli_options(
        self, project_dir
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = []

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=1,
            expected_output_contains=[
                "An entrypoint must be provided:",
            ],
        )

    async def test_deploy_single_allows_options_override(
        self, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p"
                f" {work_pool.name} --version 1.0.0 -v env=prod -t foo-bar"
            ),
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/test-name' successfully created with id"
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == work_pool.name
        assert deployment.version == "1.0.0"
        assert deployment.tags == ["foo-bar"]
        assert deployment.job_variables == {"env": "prod"}

    async def test_deploy_single_deployment_with_name_in_cli(
        self, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name-1",
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name-1",
            ],
        )

        # Check if the deployment was created correctly
        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment.name == "test-name-1"
        assert deployment.work_pool_name == work_pool.name

    @pytest.mark.parametrize(
        "deploy_names",
        [
            ("my-flow/test-name-1", "test-name-3"),
            ("my-flow/test-name-1", "my-flow/test-name-3"),
            ("test-name-1", "my-flow/test-name-3"),
            ("test-name-1", "test-name-3"),
        ],
    )
    async def test_deploy_existing_deployment_and_nonexistent_deployment_deploys_former(
        self, deploy_names, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        deploy_command = f"deploy -n '{deploy_names[0]}' -n '{deploy_names[1]}'"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=deploy_command,
            expected_code=0,
            expected_output_contains=[
                (
                    "The following deployment(s) could not be found and will not be"
                    f" deployed: {deploy_names[1].split('/')[-1]}"
                ),
                "An important name/test-name-1",
            ],
            expected_output_does_not_contain=[
                "An important name/test-name-3",
            ],
        )

        # Check if the deployment was created correctly
        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment.name == "test-name-1"
        assert deployment.work_pool_name == work_pool.name

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-3"
            )


class TestDeployPattern:
    @pytest.mark.parametrize(
        "deploy_name",
        [
            ("my-flow/test-name-*", "my-flow-test-name-2"),
            ("my-f*/test-name-1", "my-f*/test-name-2"),
            "*-name-*",
            ("my-*ow/test-name-1", "test-*-2"),
            ("*-flow/*-name-1", "*-name-2"),
            "my-flow/t*",
            ("*/test-name-1", "*/test-name-2"),
            "*/t*",
        ],
    )
    async def test_pattern_deploy_multiple_existing_deployments(
        self, deploy_name, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "dont-deploy-me",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        if isinstance(deploy_name, tuple):
            deploy_command = "deploy " + " ".join(
                [f"-n '{name}'" for name in deploy_name]
            )
        else:
            deploy_command = f"deploy -n '{deploy_name}'"

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=deploy_command,
            expected_code=0,
            expected_output_contains=[
                "Deploying flows with selected deployment configurations...",
                "An important name/test-name-1",
                "An important name/test-name-2",
            ],
            expected_output_does_not_contain=[
                "An important name/dont-deploy-me",
            ],
        )

        # Check if the deployment was created correctly
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name

        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )
        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/dont-deploy-me"
            )

    @pytest.mark.parametrize(
        "deploy_name",
        [
            "*/nonexistent-deployment-name",
            "my-f*/nonexistent-deployment-name",
            "nonexistent-deployment-name",
            "nonexistent-*-name",
            "nonexistent-flow/*",
            "nonexistent-*/nonexistent-*",
        ],
    )
    async def test_pattern_deploy_nonexistent_deployments_no_existing_deployments(
        self, deploy_name, project_dir, prefect_client, work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy -n '{deploy_name}'",
            expected_code=1,
            expected_output_contains=[
                "An entrypoint must be provided",
            ],
        )

    @pytest.mark.parametrize(
        "deploy_name",
        [
            "*/nonexistent-deployment-name",
            "my-f*/nonexistent-deployment-name",
            "nonexistent-*-name",
            "nonexistent-flow/*",
            "nonexistent-*/nonexistent-*",
        ],
    )
    async def test_pattern_deploy_nonexistent_deployments_with_existing_deployments(
        self, deploy_name, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy -n '{deploy_name}'",
            expected_code=1,
            expected_output_contains=[
                (
                    "Discovered one or more deployment configurations, but no name was"
                    " given. Please specify the name of at least one deployment to"
                    " create or update."
                ),
            ],
            expected_output_does_not_contain=[
                "An important name/test-name-1",
                "An important name/test-name-2",
            ],
        )

        # Check if the deployments were not created
        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-1"
            )

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-2"
            )

    @pytest.mark.parametrize(
        "deploy_name",
        [
            ("my-flow/test-name-*", "nonexistent-deployment"),
            ("my-f*/test-name-1", "my-f*/test-name-2", "my-f*/nonexistent-deployment"),
            ("*-name-4", "*-name-*"),
            ("my-flow/t*", "nonexistent-flow/*"),
        ],
    )
    async def test_pattern_deploy_one_existing_deployment_one_nonexistent_deployment(
        self, project_dir, prefect_client, work_pool, deploy_name
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "dont-deploy-me",
                "entrypoint": "./flows/hello.py:my_flow",
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        if isinstance(deploy_name, tuple):
            deploy_command = "deploy " + " ".join(
                [f"-n '{name}'" for name in deploy_name]
            )
        else:
            deploy_command = f"deploy -n '{deploy_name}'"

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=deploy_command,
            expected_code=0,
            expected_output_contains=[
                "Deploying flows with selected deployment configurations...",
                "An important name/test-name-1",
                "An important name/test-name-2",
            ],
            expected_output_does_not_contain=[
                (
                    "Discovered one or more deployment configurations, but no name was"
                    " given. Please specify the name of at least one deployment to"
                    " create or update."
                ),
                "An important name/dont-deploy-me",
            ],
        )

        # Check if the deployment was created correctly
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name

        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )
        assert deployment2.name == "test-name-2"

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/dont-deploy-me"
            )

    @pytest.mark.parametrize(
        "deploy_names",
        [
            ("my-flow/test-name-3", "test-name-4"),
            ("test-name-3", "my-flow/test-name-4"),
            ("test-name-3", "test-name-4"),
            ("my-flow/test-name-3", "my-flow/test-name-4"),
        ],
    )
    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_multiple_nonexistent_deployments_raises(
        self, deploy_names, work_pool, prefect_client
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        deploy_command = f"deploy -n '{deploy_names[0]}' -n '{deploy_names[1]}'"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=deploy_command,
            expected_code=1,
            expected_output_contains=[
                (
                    "The following deployment(s) could not be found and will not be"
                    f" deployed: {deploy_names[0].split('/')[-1]},"
                    f" {deploy_names[1].split('/')[-1]}"
                ),
                (
                    "Could not find any deployment configurations with the given"
                    f" name(s): {deploy_names[0]}, {deploy_names[1]}. Your flow will be"
                    " deployed with a new deployment configuration."
                ),
            ],
        )

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-3"
            )

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-4"
            )

    @pytest.mark.parametrize(
        "deploy_names",
        [
            ("my-flow/test-name-1", "my-flow/test-name-2"),
            ("test-name-1", "test-name-2"),
            ("my-flow/test-name-1", "test-name-2"),
        ],
    )
    async def test_deploy_multiple_existing_deployments_deploys_both(
        self, deploy_names, project_dir, prefect_client, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        deploy_command = f"deploy -n '{deploy_names[0]}' -n '{deploy_names[1]}'"
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=deploy_command,
            expected_code=0,
            expected_output_contains=[
                "Deploying flows with selected deployment configurations...",
                "An important name/test-name-1",
                "An important name/test-name-2",
            ],
        )

        # Check if the deployment was created correctly
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name

        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-2"
        )
        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name

    async def test_deploy_exits_with_multiple_deployments_with_no_name(
        self, project_dir
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
            },
            {
                "name": "test-name-2",
                "entrypoint": "./flows/hello.py:my_flow",
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)
        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=1,
            expected_output_contains=[
                (
                    "Discovered one or more deployment configurations, but"
                    " no name was given. Please specify the name of at least one"
                    " deployment to create or update."
                ),
            ],
        )

    @pytest.mark.parametrize(
        "deploy_names",
        [
            "test-name-1",
            "my-flow/test-name-1",
        ],
    )
    async def test_deploy_with_single_deployment_with_no_name(
        self, deploy_names, project_dir, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy -n '{deploy_names[0]}'",
            expected_code=1,
            expected_output_contains=[
                (
                    "Could not find any deployment configurations with the given"
                    f" name(s): {deploy_names[0]}. Your flow will be deployed with a"
                    " new deployment configuration."
                ),
            ],
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_with_two_deployments_with_same_name_interactive_prompts_select(
        self, work_pool, prefect_client
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow2",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n 'test-name-1'",
            user_input=(
                # select 2nd flow named my_flow2
                readchar.key.DOWN
                + readchar.key.ENTER
                # reject scheduling when flow runs
                + "n"
                + readchar.key.ENTER
                # reject saving configuration
                + "n"
                + readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Found multiple deployment configurations with the name test-name-1",
                "'Second important name/test-name-1' successfully created",
            ],
        )

        # Check if the deployment was created correctly
        deployment = await prefect_client.read_deployment_by_name(
            "Second important name/test-name-1"
        )
        assert deployment.name == "test-name-1"
        assert deployment.work_pool_name == work_pool.name

        with pytest.raises(ObjectNotFound):
            await prefect_client.read_deployment_by_name(
                "An important name/test-name-1"
            )

    @pytest.mark.usefixtures("project_dir")
    async def test_deploy_with_two_deployments_with_same_name_noninteractive_deploys_both(
        self, work_pool, prefect_client
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            },
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow2",
                "work_pool": {"name": work_pool.name},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n 'test-name-1'",
            expected_code=0,
            expected_output_contains=[
                "Deploying flows with selected deployment configurations...",
                "'An important name/test-name-1' successfully created",
                "'Second important name/test-name-1' successfully created",
            ],
        )

        # Check if the deployments were created correctly
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name

        deployment2 = await prefect_client.read_deployment_by_name(
            "Second important name/test-name-1"
        )
        assert deployment2.name == "test-name-1"
        assert deployment2.work_pool_name == work_pool.name

    async def test_deploy_warns_with_single_deployment_and_multiple_names(
        self, project_dir, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name-1 -n test-name-2",
            expected_code=0,
            expected_output_contains=[
                (
                    "The following deployment(s) could not be found and will not be"
                    " deployed: test-name-2"
                ),
            ],
        )

    @pytest.mark.usefixtures("project_dir")
    async def test_concurrency_limit_config_deployment_yaml(
        self, work_pool, prefect_client: PrefectClient
    ):
        concurrency_limit_config = {"limit": 42, "collision_strategy": "CANCEL_NEW"}

        prefect_yaml = Path("prefect.yaml")
        with prefect_yaml.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["concurrency_limit"] = concurrency_limit_config

        with prefect_yaml.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(f"deploy ./flows/hello.py:my_flow --pool {work_pool.name}"),
        )
        assert result.exit_code == 0

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )

        assert deployment.global_concurrency_limit is not None
        assert (
            deployment.global_concurrency_limit.limit
            == concurrency_limit_config["limit"]
        )
        assert deployment.concurrency_options is not None
        assert (
            deployment.concurrency_options.collision_strategy
            == concurrency_limit_config["collision_strategy"]
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_select_from_existing_deployments(
        self, work_pool, prefect_client
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"] = [
            {
                "name": "test-name-1",
                "description": "test-description-1",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
            {
                "name": "test-name-2",
                "description": "test-description-2",
                "entrypoint": "./flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name},
                "schedule": {"interval": 3600},
            },
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=0,
            user_input=(
                readchar.key.ENTER
                # decline remote storage
                + "n"
                + readchar.key.ENTER
                # reject saving configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to use an existing deployment configuration?",
                "test-name-1",
                "test-name-2",
                "test-description-1",
                "test-description-2",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        assert deployment.name == "test-name-1"


@pytest.mark.usefixtures("interactive_console", "project_dir")
class TestSaveUserInputs:
    def test_save_user_inputs_no_existing_prefect_file(self):
        prefect_file = Path("prefect.yaml")
        prefect_file.unlink()
        assert not prefect_file.exists()

        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # Accept default deployment name
                readchar.key.ENTER
                +
                # decline schedule
                "n"
                + readchar.key.ENTER
                +
                # accept create work pool
                readchar.key.ENTER
                +
                # choose process work pool
                readchar.key.ENTER
                +
                # enter work pool name
                "inflatable"
                + readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        assert prefect_file.exists()
        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 1
        assert config["deployments"][0]["name"] == "default"
        assert config["deployments"][0]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][0]["schedules"] == []
        assert config["deployments"][0]["work_pool"]["name"] == "inflatable"

    def test_save_user_inputs_existing_prefect_file(self):
        prefect_file = Path("prefect.yaml")
        assert prefect_file.exists()

        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # Accept default deployment name
                readchar.key.ENTER
                +
                # decline schedule
                "n"
                + readchar.key.ENTER
                +
                # accept create work pool
                readchar.key.ENTER
                +
                # choose process work pool
                readchar.key.ENTER
                +
                # enter work pool name
                "inflatable"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["schedules"] == []
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

    def test_save_user_inputs_with_interval_schedule(self):
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            prompts_and_responses=[
                ("? Deployment name (default)", ""),
                ("Would you like to configure schedules for this deployment?", ""),
                ("What type of schedule would you like to use?", "", "Interval"),
                ("Seconds between scheduled runs", "3600"),
                ("Would you like to activate this schedule?", "y"),
                ("Would you like to add another schedule?", "n"),
                ("you don't have any work pools", "y"),
                ("What infrastructure type", "", "process"),
                ("Work pool name", "inflatable"),
                ("Would you like to save configuration", "y"),
            ],
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        with open("prefect.yaml", mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

        schedule = config["deployments"][1]["schedules"][0]
        assert schedule["interval"] == 3600
        assert schedule["timezone"] == "UTC"
        assert schedule["anchor_date"] is not None
        assert schedule["active"]

    def test_save_user_inputs_with_cron_schedule(self):
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            prompts_and_responses=[
                ("? Deployment name (default)", ""),
                ("Would you like to configure schedules for this deployment?", ""),
                ("What type of schedule would you like to use?", "↓", "Cron"),
                ("Cron string (0 0 * * *)", "* * * * *"),
                ("Timezone (UTC)", ""),
                ("Would you like to activate this schedule?", "y"),
                ("Would you like to add another schedule?", "n"),
                ("you don't have any work pools", "y"),
                ("What infrastructure type", "", "process"),
                ("Work pool name", "inflatable"),
                ("Would you like to save configuration", "y"),
            ],
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        with open("prefect.yaml", mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

        schedule = config["deployments"][1]["schedules"][0]
        assert schedule == {
            "cron": "* * * * *",
            "day_or": True,
            "timezone": "UTC",
            "active": True,
            "max_active_runs": None,
            "catchup": False,
        }

    def test_deploy_existing_deployment_with_no_changes_does_not_prompt_save(self):
        # Set up initial deployment deployment
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            prompts_and_responses=[
                ("? Deployment name (default)", "existing-deployment"),
                ("Would you like to configure schedules for this deployment?", ""),
                ("What type of schedule would you like to use?", "↓", "Cron"),
                ("Cron string (0 0 * * *)", "* * * * *"),
                ("Timezone (UTC)", ""),
                ("Would you like to activate this schedule?", "y"),
                ("Would you like to add another schedule?", "n"),
                ("you don't have any work pools", "y"),
                ("What infrastructure type", "", "process"),
                ("Work pool name", "inflatable"),
                ("Would you like to save configuration", "y"),
            ],
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2

        assert config["deployments"][1]["name"] == "existing-deployment"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"
        assert config["deployments"][1]["schedules"][0] == {
            "cron": "* * * * *",
            "day_or": True,
            "timezone": "UTC",
            "active": True,
            "max_active_runs": None,
            "catchup": False,
        }

        invoke_and_assert(
            command="deploy -n existing-deployment --cron '* * * * *'",
            prompts_and_responses=[
                ("Would you like to save configuration", "y"),
                ("Would you like to overwrite that entry?", "y"),
            ],
            expected_code=0,
            expected_output_does_not_contain=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                    "Deployment configuration saved to prefect.yaml"
                ),
            ],
        )

        # assert that the deployment was updated in the prefect.yaml
        with open("prefect.yaml", mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "existing-deployment"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"
        assert config["deployments"][1]["schedules"][0] == {
            "cron": "* * * * *",
            "day_or": True,
            "timezone": "UTC",
            "active": True,
            "max_active_runs": None,
            "catchup": False,
        }

    def test_deploy_existing_deployment_with_changes_prompts_save(self):
        # Set up initial deployment deployment
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # enter deployment name
                "existing-deployment"
                + readchar.key.ENTER
                # reject create schedule
                + "n"
                + readchar.key.ENTER
                +
                # accept create work pool
                readchar.key.ENTER
                +
                # choose process work pool
                readchar.key.ENTER
                +
                # enter work pool name
                "inflatable"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2

        assert config["deployments"][1]["name"] == "existing-deployment"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"
        assert config["deployments"][1]["schedules"] == []

        invoke_and_assert(
            command="deploy -n existing-deployment --cron '* * * * *'",
            user_input=(
                # accept create work pool
                readchar.key.ENTER
                # choose process work pool
                + readchar.key.ENTER
                +
                # enter work pool name
                "inflatable"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
                # accept found existing deployment
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        # assert that the deployment was updated in the prefect.yaml
        with open("prefect.yaml", mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "existing-deployment"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"
        assert config["deployments"][1]["schedules"][0]["cron"] == "* * * * *"

    def test_save_user_inputs_with_rrule_schedule(self):
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # Accept default deployment name
                readchar.key.ENTER
                +
                # accept schedule
                readchar.key.ENTER
                +
                # select rrule schedule
                readchar.key.DOWN
                + readchar.key.DOWN
                + readchar.key.ENTER
                +
                # enter rrule schedule
                "FREQ=MINUTELY"
                + readchar.key.ENTER
                # accept schedule being active
                + readchar.key.ENTER
                # decline adding another schedule
                + readchar.key.ENTER
                # accept create work pool
                + readchar.key.ENTER
                +
                # accept create work pool
                readchar.key.ENTER
                +
                # choose process work pool
                readchar.key.ENTER
                +
                # enter work pool name
                "inflatable"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        with open("prefect.yaml", mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

        schedule = config["deployments"][1]["schedules"][0]
        assert schedule == {
            "rrule": "FREQ=MINUTELY",
            "timezone": "UTC",
            "active": True,
            "max_active_runs": None,
            "catchup": False,
        }

    async def test_save_user_inputs_with_actions(self):
        new_deployment_to_save = {
            "name": "new_deployment",
            "entrypoint": "flows/new_flow.py:my_flow",
            "schedule": None,
            "work_pool": {"name": "new_pool"},
            "parameter_openapi_schema": None,
        }

        build_steps = [
            {
                "prefect.steps.set_working_directory": {
                    "directory": "/path/to/working/directory"
                }
            },
        ]

        push_steps = [
            {
                "prefect_aws.deployments.steps.push_to_s3": {
                    "requires": "prefect-aws>=0.3.0",
                    "bucket": "my-bucket",
                    "folder": "project-name",
                    "credentials": None,
                }
            },
        ]

        pull_steps = [
            {
                "prefect_aws.deployments.steps.pull_from_s3": {
                    "requires": "prefect-aws>=0.3.0",
                    "bucket": "my-bucket",
                    "folder": "{{ push-code.folder }}",
                    "credentials": None,
                }
            },
        ]

        _save_deployment_to_prefect_file(
            new_deployment_to_save,
            build_steps=build_steps,
            push_steps=push_steps,
            pull_steps=pull_steps,
        )

        prefect_file = Path("prefect.yaml")
        assert prefect_file.exists()

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == new_deployment_to_save["name"]
        assert (
            config["deployments"][1]["entrypoint"]
            == new_deployment_to_save["entrypoint"]
        )
        assert (
            config["deployments"][1]["work_pool"]["name"]
            == new_deployment_to_save["work_pool"]["name"]
        )
        assert (
            config["deployments"][1]["schedule"] == new_deployment_to_save["schedule"]
        )
        assert config["deployments"][1]["build"] == build_steps
        assert config["deployments"][1]["push"] == push_steps
        assert config["deployments"][1]["pull"] == pull_steps

    def test_save_new_deployment_with_same_name_as_existing_deployment_overwrites(self):
        # Set up initial 'prefect.yaml' file with a deployment
        initial_deployment = {
            "name": "existing_deployment",
            "entrypoint": "flows/existing_flow.py:my_flow",
            "schedule": None,
            "work_pool": {"name": "existing_pool"},
            "parameter_openapi_schema": None,
        }

        _save_deployment_to_prefect_file(initial_deployment)

        prefect_file = Path("prefect.yaml")
        assert prefect_file.exists()

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2

        assert config["deployments"][1]["name"] == initial_deployment["name"]

        # Overwrite the existing deployment
        new_deployment = {
            "name": "existing_deployment",
            "entrypoint": "flows/existing_flow.py:my_flow",
            "schedule": None,
            "concurrency_limit": 42,
            "work_pool": {"name": "new_pool"},
            "parameter_openapi_schema": None,
        }

        _save_deployment_to_prefect_file(new_deployment)

        # Check that the new deployment has overwritten the old one
        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == new_deployment["name"]
        assert config["deployments"][1]["entrypoint"] == new_deployment["entrypoint"]
        assert (
            config["deployments"][1]["concurrency_limit"]
            == new_deployment["concurrency_limit"]
        )
        assert (
            config["deployments"][1]["work_pool"]["name"]
            == new_deployment["work_pool"]["name"]
        )

    def test_save_user_inputs_overwrite_confirmed(self):
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # Accept default deployment name
                readchar.key.ENTER
                # decline schedule
                + "n"
                + readchar.key.ENTER
                # accept create work pool
                + readchar.key.ENTER
                # choose process work pool
                + readchar.key.ENTER
                # enter work pool name
                + "inflatable"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )
        prefect_file = Path("prefect.yaml")

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)
        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["schedules"] == []
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # Configure new deployment
                "n"
                + readchar.key.ENTER
                +
                # accept schedule
                readchar.key.ENTER
                +
                # select interval schedule
                readchar.key.ENTER
                +
                # enter interval schedule
                "3600"
                + readchar.key.ENTER
                +
                # accept create work pool
                readchar.key.ENTER
                +
                # choose process work pool
                readchar.key.ENTER
                +
                # enter work pool name
                "inflatable"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
                # accept overwriting existing deployment that is found
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Found existing deployment configuration",
                "Deployment configuration saved to prefect.yaml",
            ],
        )

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["schedules"][0]["interval"] == 3600
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

    def test_save_user_inputs_overwrite_rejected_saving_cancelled(self):
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # accept default deployment name
                readchar.key.ENTER
                +
                # decline schedule
                "n"
                + readchar.key.ENTER
                +
                # accept create work pool
                readchar.key.ENTER
                +
                # choose process work pool
                readchar.key.ENTER
                +
                # enter work pool name
                "inflatable"
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Deployment configuration saved to prefect.yaml",
            ],
        )
        prefect_file = Path("prefect.yaml")

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)
        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["schedules"] == []
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # configure new deployment
                "n"
                + readchar.key.ENTER
                # configure schedule
                + readchar.key.ENTER
                # select interval schedule
                + readchar.key.ENTER
                # enter interval schedule
                + "3600"
                + readchar.key.ENTER
                # accept schedule being active
                + readchar.key.ENTER
                # decline adding another schedule
                + readchar.key.ENTER
                # accept existing work pool
                + readchar.key.ENTER
                # accept save user inputs
                + "y"
                + readchar.key.ENTER
                # reject overwriting existing deployment that is found
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Found existing deployment configuration",
                "Cancelled saving deployment configuration",
            ],
        )

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "default"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["schedules"] == []
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

    @pytest.mark.usefixtures("project_dir", "interactive_console")
    async def test_deploy_resolves_block_references_in_deployments_section(
        self, prefect_client, work_pool, ignore_prefect_deprecation_warnings
    ):
        """
        Ensure block references are resolved in deployments section of prefect.yaml
        """
        # TODO: Remove this test when `JSON` block is removed
        await JSON(value={"work_pool_name": work_pool.name}).save(
            name="test-json-block"
        )

        # add block reference to prefect.yaml
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        prefect_config["deployments"] = [
            {
                "name": "test-name",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {
                    "name": (
                        "{{ prefect.blocks.json.test-json-block.value.work_pool_name }}"
                    ),
                },
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        # ensure block reference was added
        assert (
            prefect_config["deployments"][0]["work_pool"]["name"]
            == "{{ prefect.blocks.json.test-json-block.value.work_pool_name }}"
        )

        # run deploy
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy flows/hello.py:my_flow -n test-name",
            user_input=(
                # reject schedule
                "n"
                + readchar.key.ENTER
                # accept saving configuration
                + "y"
                + readchar.key.ENTER
                # accept overwrite config
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/test-name' successfully created",
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Would you like",
                "to overwrite that entry?",
                "Deployment configuration saved to prefect.yaml!",
            ],
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == work_pool.name

        # ensure block reference was resolved
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        assert prefect_config["deployments"][0]["work_pool"]["name"] == work_pool.name

    @pytest.mark.usefixtures("project_dir", "interactive_console")
    async def test_deploy_resolves_variables_in_deployments_section(
        self, prefect_client, work_pool
    ):
        """
        Ensure deployments section of prefect.yaml placeholders are resolved
        """
        # create variable
        await prefect_client._client.post(
            "/variables/", json={"name": "my_work_pool", "value": work_pool.name}
        )

        # add variable to deployments section of prefect.yaml
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        prefect_config["deployments"] = [
            {
                "name": "test-name",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {
                    "name": "{{ prefect.variables.my_work_pool }}",
                },
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        # ensure it is there!
        assert (
            prefect_config["deployments"][0]["work_pool"]["name"]
            == "{{ prefect.variables.my_work_pool }}"
        )

        # run deploy
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy flows/hello.py:my_flow -n test-name",
            user_input=(
                # reject schedule
                "n"
                + readchar.key.ENTER
                # accept saving configuration
                + "y"
                + readchar.key.ENTER
                # accept overwrite config
                + "y"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Deployment 'An important name/test-name' successfully created",
                (
                    "Would you like to save configuration for this deployment for"
                    " faster deployments in the future?"
                ),
                "Would you like",
                "to overwrite that entry?",
                "Deployment configuration saved to prefect.yaml!",
            ],
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == work_pool.name

        # ensure variable is resolved in prefect.yaml
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        assert prefect_config["deployments"][0]["work_pool"]["name"] == work_pool.name


@pytest.mark.usefixtures("project_dir", "interactive_console", "work_pool")
class TestDeployWithoutEntrypoint:
    async def test_deploy_without_entrypoint(self, prefect_client: PrefectClient):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            user_input=(
                # Accept first flow
                readchar.key.ENTER
                +
                # Accept default deployment name
                readchar.key.ENTER
                +
                # decline schedule
                "n"
                + readchar.key.ENTER
                +
                # accept first work pool
                readchar.key.ENTER
                +
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                +
                # decline save user inputs
                "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Select a flow to deploy",
                "test_flow",
                "import-project/my_module/flow.py",
                "prod_flow",
                "import-project/my_module/flow.py",
                "foobar",
                "nested-project/implicit_relative.py",
                "nested-project/explicit_relative.py",
                "my_flow",
                "flows/hello.py",
                "successfully created",
            ],
        )

    async def test_deploy_without_entrypoint_manually_enter(
        self, prefect_client: PrefectClient
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            user_input=(
                # Decline selecting from list
                "n"
                +
                # Enter entrypoint
                "flows/hello.py:my_flow"
                + readchar.key.ENTER
                +
                # Accept default deployment name
                readchar.key.ENTER
                +
                # decline schedule
                "n"
                + readchar.key.ENTER
                +
                # accept first work pool
                readchar.key.ENTER
                +
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                +
                # decline save user inputs
                "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Select a flow to deploy",
                "Flow entrypoint (expected format path/to/file.py:function_name)",
                "Deployment 'An important name/default' successfully created",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            name="An important name/default"
        )
        assert deployment.entrypoint == "flows/hello.py:my_flow"

    async def test_deploy_validates_manually_entered_entrypoints(
        self, prefect_client: PrefectClient
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            user_input=(
                # Decline selecting from list
                "n"
                +
                # Enter syntactically invalid entrypoint
                "flows/hello.py"
                + readchar.key.ENTER
                +
                # Enter entrypoint with non-existent file
                "flows/does_not_exist.py:my_flow"
                + readchar.key.ENTER
                +
                # Enter entrypoint with non-existent function
                "flows/hello.py:does_not_exist"
                + readchar.key.ENTER
                +
                # Enter valid entrypoint
                "flows/hello.py:my_flow"
                + readchar.key.ENTER
                +
                # Accept default deployment name
                readchar.key.ENTER
                +
                # decline schedule
                "n"
                + readchar.key.ENTER
                +
                # accept first work pool
                readchar.key.ENTER
                +
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                +
                # decline save user inputs
                "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Select a flow to deploy",
                "Please enter a valid flow entrypoint.",
                "Failed to load flow from entrypoint 'flows/does_not_exist.py:my_flow'",
                "Failed to load flow from entrypoint 'flows/hello.py:does_not_exist'",
                "Deployment 'An important name/default' successfully created",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            name="An important name/default"
        )
        assert deployment.entrypoint == "flows/hello.py:my_flow"


class TestCheckForMatchingDeployment:
    @pytest.fixture(autouse=True)
    def in_temporary_directory(self, tmp_path: Path):
        with tmpchdir(tmp_path):
            yield

    async def test_matching_deployment_in_prefect_file_returns_true(self):
        deployment = {
            "name": "existing_deployment",
            "entrypoint": "flows/existing_flow.py:my_flow",
            "schedule": None,
            "work_pool": {"name": "existing_pool"},
            "parameter_openapi_schema": None,
        }
        _save_deployment_to_prefect_file(deployment)

        prefect_file = Path("prefect.yaml")

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        matching_deployment_exists = any(
            d["name"] == deployment["name"]
            and d["entrypoint"] == deployment["entrypoint"]
            for d in config["deployments"]
        )

        assert matching_deployment_exists, "No matching deployment found in the file."

        new_deployment = {
            "name": "existing_deployment",
            "entrypoint": "flows/existing_flow.py:my_flow",
        }
        matching_deployment_exists = (
            _check_for_matching_deployment_name_and_entrypoint_in_prefect_file(
                new_deployment
            )
        )
        assert matching_deployment_exists is True

    async def test_no_matching_deployment_in_prefect_file_returns_false(self):
        deployment = {
            "name": "existing_deployment",
            "entrypoint": "flows/existing_flow.py:my_flow",
            "schedule": None,
            "work_pool": {"name": "existing_pool"},
            "parameter_openapi_schema": None,
        }
        _save_deployment_to_prefect_file(deployment)

        prefect_file = Path("prefect.yaml")

        with prefect_file.open(mode="r") as f:
            config = yaml.safe_load(f)

        matching_deployment_exists = any(
            d["name"] == deployment["name"]
            and d["entrypoint"] == deployment["entrypoint"]
            for d in config["deployments"]
        )

        assert matching_deployment_exists

        deployment_with_same_entrypoint_but_different_name = {
            "name": "new_deployment",
            "entrypoint": "flows/existing_flow.py:my_flow",
        }
        matching_deployment_exists_1 = (
            _check_for_matching_deployment_name_and_entrypoint_in_prefect_file(
                deployment_with_same_entrypoint_but_different_name
            )
        )
        assert not matching_deployment_exists_1

        deployment_with_same_name_but_different_entrypoint = {
            "name": "new_deployment",
            "entrypoint": "flows/new_flow.py:my_flow",
        }
        matching_deployment_exists_2 = (
            _check_for_matching_deployment_name_and_entrypoint_in_prefect_file(
                deployment_with_same_name_but_different_entrypoint
            )
        )
        assert not matching_deployment_exists_2


class TestDeploymentTrigger:
    class TestDeploymentTriggerSyncing:
        async def test_initialize_named_deployment_triggers(self):
            trigger_spec = {
                "name": "Trigger McTriggerson",
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "match_related": {
                    "prefect.resource.name": "seed",
                    "prefect.resource.role": "flow",
                },
                "job_variables": {"foo": "bar"},
            }

            triggers = _initialize_deployment_triggers("my_deployment", [trigger_spec])
            assert triggers == [
                DeploymentEventTrigger(
                    **{
                        "name": "Trigger McTriggerson",
                        "description": "",
                        "enabled": True,
                        "match": {"prefect.resource.id": "prefect.flow-run.*"},
                        "match_related": {
                            "prefect.resource.name": "seed",
                            "prefect.resource.role": "flow",
                        },
                        "after": set(),
                        "expect": {"prefect.flow-run.Completed"},
                        "for_each": set(),
                        "posture": Posture.Reactive,
                        "threshold": 1,
                        "within": timedelta(0),
                        "job_variables": {"foo": "bar"},
                    }
                )
            ]

        async def test_initialize_deployment_triggers_composite(self):
            trigger_spec = {
                "name": "Trigger McTriggerson",
                "enabled": True,
                "type": "compound",
                "require": "all",
                "job_variables": {"foo": "bar"},
                "triggers": [
                    {
                        "type": "event",
                        "match": {"prefect.resource.id": "prefect.flow-run.*"},
                        "match_related": {
                            "prefect.resource.name": "seed",
                            "prefect.resource.role": "flow",
                        },
                        "expect": {"prefect.flow-run.Completed"},
                    }
                ],
            }

            triggers = _initialize_deployment_triggers("my_deployment", [trigger_spec])
            assert triggers == [
                DeploymentCompoundTrigger(
                    **{
                        "name": "Trigger McTriggerson",
                        "enabled": True,
                        "require": "all",
                        "job_variables": {"foo": "bar"},
                        "triggers": [
                            EventTrigger(
                                **{
                                    "enabled": True,
                                    "match": {
                                        "prefect.resource.id": "prefect.flow-run.*"
                                    },
                                    "match_related": {
                                        "prefect.resource.name": "seed",
                                        "prefect.resource.role": "flow",
                                    },
                                    "after": set(),
                                    "expect": {"prefect.flow-run.Completed"},
                                    "for_each": set(),
                                    "posture": Posture.Reactive,
                                    "threshold": 1,
                                    "within": timedelta(0),
                                    "job_variables": {"foo": "bar"},
                                }
                            )
                        ],
                    }
                )
            ]

        async def test_initialize_deployment_triggers_implicit_name(self):
            trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "match_related": {
                    "prefect.resource.name": "seed",
                    "prefect.resource.role": "flow",
                },
            }

            triggers = _initialize_deployment_triggers("my_deployment", [trigger_spec])
            assert triggers[0].name == "my_deployment__automation_1"

        async def test_deployment_triggers_without_job_variables(self):
            trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "match_related": {
                    "prefect.resource.name": "seed",
                    "prefect.resource.role": "flow",
                },
            }

            triggers = _initialize_deployment_triggers("my_deployment", [trigger_spec])
            assert triggers[0].job_variables is None

        async def test_create_deployment_triggers(self):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "match_related": {
                    "prefect.resource.name": "seed",
                    "prefect.resource.role": "flow",
                },
                "job_variables": {"nested": {"foo": "bar"}},
            }

            triggers = _initialize_deployment_triggers("my_deployment", [trigger_spec])
            deployment_id = uuid4()

            await _create_deployment_triggers(client, deployment_id, triggers)

            assert triggers[0]._deployment_id == deployment_id
            client.delete_resource_owned_automations.assert_called_once_with(
                f"prefect.deployment.{deployment_id}"
            )
            client.create_automation.assert_called_once_with(
                triggers[0].as_automation()
            )

        async def test_triggers_creation_orchestrated(
            self, project_dir, prefect_client, work_pool
        ):
            prefect_file = Path("prefect.yaml")
            with prefect_file.open(mode="r") as f:
                contents = yaml.safe_load(f)

            contents["deployments"] = [
                {
                    "name": "test-name-1",
                    "work_pool": {
                        "name": work_pool.name,
                    },
                    "triggers": [
                        {
                            "enabled": True,
                            "match": {"prefect.resource.id": "prefect.flow-run.*"},
                            "expect": ["prefect.flow-run.Completed"],
                            "match_related": {
                                "prefect.resource.name": "seed",
                                "prefect.resource.role": "flow",
                            },
                            "job_variables": {"foo": 123},
                        }
                    ],
                }
            ]

            expected_triggers = _initialize_deployment_triggers(
                "test-name-1", contents["deployments"][0]["triggers"]
            )

            with prefect_file.open(mode="w") as f:
                yaml.safe_dump(contents, f)

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ) as create_triggers:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command="deploy ./flows/hello.py:my_flow -n test-name-1",
                    expected_code=0,
                )

                assert create_triggers.call_count == 1

                client, deployment_id, triggers = create_triggers.call_args[0]
                assert isinstance(client, PrefectClient)
                assert isinstance(deployment_id, UUID)

                expected_triggers[0].set_deployment_id(deployment_id)

                assert triggers == expected_triggers

    class TestDeploymentTriggerPassedViaCLI:
        @pytest.mark.usefixtures("project_dir")
        async def test_json_string_trigger(self, docker_work_pool):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "job_variables": {"foo": "bar"},
                "within": 60,
                "threshold": 2,
            }

            expected_triggers = _initialize_deployment_triggers(
                "test-name-1", [trigger_spec]
            )

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ) as create_triggers:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1 --trigger"
                        f" '{json.dumps(trigger_spec)}' -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_triggers.call_count == 1

                client, deployment_id, triggers = create_triggers.call_args[0]

                expected_triggers[0].set_deployment_id(deployment_id)

                assert triggers == expected_triggers

        @pytest.mark.usefixtures("project_dir")
        async def test_json_file_trigger(self, docker_work_pool):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "job_variables": {"foo": "bar"},
            }

            with open("triggers.json", "w") as f:
                json.dump({"triggers": [trigger_spec]}, f)

            expected_triggers = _initialize_deployment_triggers(
                "test-name-1", [trigger_spec]
            )

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ) as create_triggers:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --trigger triggers.json -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_triggers.call_count == 1

                client, deployment_id, triggers = create_triggers.call_args[0]

                expected_triggers[0].set_deployment_id(deployment_id)

                assert triggers == expected_triggers

        @pytest.mark.usefixtures("project_dir")
        async def test_yaml_file_trigger(self, docker_work_pool):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "job_variables": {"foo": "bar"},
            }

            with open("triggers.yaml", "w") as f:
                yaml.safe_dump({"triggers": [trigger_spec]}, f)

            expected_triggers = _initialize_deployment_triggers(
                "test-name-1", [trigger_spec]
            )

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ) as create_triggers:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --trigger triggers.yaml -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_triggers.call_count == 1

                client, deployment_id, triggers = create_triggers.call_args[0]

                expected_triggers[0].set_deployment_id(deployment_id)

                assert triggers == expected_triggers

        @pytest.mark.usefixtures("project_dir")
        async def test_nested_yaml_file_trigger(self, docker_work_pool, tmpdir):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
            }
            triggers_file = tmpdir.mkdir("my_stuff") / "triggers.yaml"
            with open(triggers_file, "w") as f:
                yaml.safe_dump({"triggers": [trigger_spec]}, f)

            expected_triggers = _initialize_deployment_triggers(
                "test-name-1", [trigger_spec]
            )

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ) as create_triggers:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --trigger my_stuff/triggers.yaml -p {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_triggers.call_count == 1

                client, deployment_id, triggers = create_triggers.call_args[0]

                expected_triggers[0].set_deployment_id(deployment_id)

                assert triggers == expected_triggers

        @pytest.mark.usefixtures("project_dir")
        async def test_multiple_trigger_flags(self, docker_work_pool):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            trigger_spec_1 = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
                "job_variables": {"foo": "bar"},
            }

            trigger_spec_2 = {
                "enabled": False,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Failed"],
            }

            with open("triggers.yaml", "w") as f:
                yaml.safe_dump({"triggers": [trigger_spec_2]}, f)

            expected_triggers = _initialize_deployment_triggers(
                "test-name-1", [trigger_spec_1, trigger_spec_2]
            )

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ) as create_triggers:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1 --trigger"
                        f" '{json.dumps(trigger_spec_1)}' --trigger triggers.yaml -p"
                        f" {docker_work_pool.name}"
                    ),
                    expected_code=0,
                )

                assert create_triggers.call_count == 1

                client, deployment_id, triggers = create_triggers.call_args[0]

                for expected_trigger in expected_triggers:
                    expected_trigger.set_deployment_id(deployment_id)

                assert triggers == expected_triggers

        @pytest.mark.usefixtures("project_dir")
        async def test_override_on_trigger_conflict(self, docker_work_pool):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            cli_trigger_spec = {
                "enabled": True,
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Failed"],
            }

            expected_triggers = _initialize_deployment_triggers(
                "test-name-1", [cli_trigger_spec]
            )

            prefect_file = Path("prefect.yaml")
            with prefect_file.open(mode="r") as f:
                contents = yaml.safe_load(f)

            contents["deployments"] = [
                {
                    "name": "test-name-1",
                    "work_pool": {
                        "name": docker_work_pool.name,
                    },
                    "triggers": [
                        {**cli_trigger_spec, "expect": ["prefect.flow-run.Completed"]}
                    ],
                }
            ]

            with prefect_file.open(mode="w") as f:
                yaml.safe_dump(contents, f)

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ) as create_triggers:
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1"
                        f" --trigger '{json.dumps(cli_trigger_spec)}'"
                    ),
                    expected_code=0,
                )

                _, _, triggers = create_triggers.call_args[0]
                assert len(triggers) == 1
                assert triggers == expected_triggers

        @pytest.mark.usefixtures("project_dir")
        async def test_invalid_trigger_parsing(self, docker_work_pool):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            invalid_json_str_trigger = "{enabled: true, match: woodchonk.move.*}"
            invalid_yaml_trigger = "invalid.yaml"

            with open(invalid_yaml_trigger, "w") as f:
                f.write("pretty please, trigger my flow when you see the woodchonk")

            for invalid_trigger in [invalid_json_str_trigger, invalid_yaml_trigger]:
                with mock.patch(
                    "prefect.cli.deploy._create_deployment_triggers",
                    AsyncMock(),
                ):
                    await run_sync_in_worker_thread(
                        invoke_and_assert,
                        command=(
                            "deploy ./flows/hello.py:my_flow -n test-name-1"
                            f" -p {docker_work_pool.name} --trigger '{invalid_trigger}'"
                        ),
                        expected_code=1,
                        expected_output_contains=["Failed to parse trigger"],
                    )

        @pytest.mark.usefixtures("interactive_console", "project_dir")
        async def test_triggers_saved_to_prefect_yaml(self, docker_work_pool):
            client = AsyncMock()
            client.server_type = ServerType.CLOUD

            cli_trigger_spec = {
                "name": "Trigger McTriggerson",
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Completed"],
            }

            with mock.patch(
                "prefect.cli.deploy._create_deployment_triggers",
                AsyncMock(),
            ):
                await run_sync_in_worker_thread(
                    invoke_and_assert,
                    command=(
                        "deploy ./flows/hello.py:my_flow -n test-name-1 -p"
                        f" {docker_work_pool.name} --trigger"
                        f" '{json.dumps(cli_trigger_spec)}'"
                    ),
                    user_input=(
                        # Decline schedule
                        "n"
                        + readchar.key.ENTER
                        # Decline docker build
                        + "n"
                        + readchar.key.ENTER
                        # Accept save configuration
                        + "y"
                        + readchar.key.ENTER
                    ),
                    expected_code=0,
                )

            # Read the updated prefect.yaml
            prefect_file = Path("prefect.yaml")
            with prefect_file.open(mode="r") as f:
                contents = yaml.safe_load(f)

            assert "deployments" in contents
            assert "triggers" in contents["deployments"][-1]
            assert contents["deployments"][-1]["triggers"] == [cli_trigger_spec]


@pytest.mark.usefixtures("project_dir", "interactive_console", "work_pool")
class TestDeployDockerBuildSteps:
    async def test_docker_build_step_exists_does_not_prompt_build_custom_docker_image(
        self,
        docker_work_pool,
        mock_build_docker_image,
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        with open("Dockerfile", "w") as f:
            f.write("FROM python:3.9-slim\n")

        prefect_config["build"] = [
            {
                "prefect_docker.deployments.steps.build_docker_image": {
                    "requires": "prefect-docker",
                    "image_name": "local/repo",
                    "tag": "dev",
                    "id": "build-image",
                    "dockerfile": "Dockerfile",
                }
            }
        ]

        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600 -p"
                f" {docker_work_pool.name}"
            ),
            user_input=(
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                +
                # Accept save configuration
                "y"
                + readchar.key.ENTER
            ),
            expected_output_does_not_contain=[
                "Would you like to build a custom Docker image"
            ],
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

    async def test_other_build_step_exists_prompts_build_custom_docker_image(
        self,
        docker_work_pool,
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            prefect_config = yaml.safe_load(f)

        prefect_config["build"] = [
            {
                "prefect.deployments.steps.run_shell_script": {
                    "id": "sample-bash-cmd",
                    "script": "echo 'Hello, World!'",
                    "stream_output": False,
                }
            }
        ]

        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Reject build custom docker image
                "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Would you like to save configuration for this deployment",
            ],
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        prefect_file = Path("prefect.yaml")

        with open(prefect_file, "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "test-name"
        assert not config["deployments"][1].get("build")

    async def test_no_build_step_exists_prompts_build_custom_docker_image(
        self, docker_work_pool
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Reject build custom docker image
                "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Would you like to save configuration for this deployment",
            ],
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        prefect_file = Path("prefect.yaml")

        with open(prefect_file, "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "test-name"
        assert not config["deployments"][1].get("build")

    async def test_prompt_build_custom_docker_image_accepted_use_existing_dockerfile_accepted(
        self, docker_work_pool, mock_build_docker_image
    ):
        with open("Dockerfile", "w") as f:
            f.write("FROM python:3.9-slim\n")

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Accept use existing dockerfile
                + "y"
                + readchar.key.ENTER
                # Enter repo name
                + "prefecthq/prefect"
                + readchar.key.ENTER
                +
                # Default image_name
                readchar.key.ENTER
                +
                # Default tag
                readchar.key.ENTER
                +
                # Reject push to registry
                "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Would you like to use the Dockerfile in the current directory?",
                "Image prefecthq/prefect/test-name:latest will be built",
                "Would you like to push this image to a remote registry?",
                "Would you like to save configuration for this deployment",
            ],
            expected_output_does_not_contain=["Is this a private registry?"],
        )

        assert result.exit_code == 0
        assert "An important name/test" in result.output
        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "test-name"
        assert config["deployments"][1]["build"] == [
            {
                "prefect_docker.deployments.steps.build_docker_image": {
                    "id": "build-image",
                    "requires": "prefect-docker>=0.3.1",
                    "dockerfile": "Dockerfile",
                    "image_name": "prefecthq/prefect/test-name",
                    "tag": "latest",
                }
            }
        ]

    async def test_prompt_build_custom_docker_image_accepted_use_existing_dockerfile_rejected_rename_accepted(
        self, docker_work_pool, monkeypatch, mock_build_docker_image
    ):
        with open("Dockerfile", "w") as f:
            f.write("FROM python:3.9-slim\n")

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Reject use existing dockerfile
                + "n"
                + readchar.key.ENTER
                # Accept rename dockerfile
                + "y"
                + readchar.key.ENTER
                +
                # Enter new dockerfile name
                "Dockerfile.backup"
                + readchar.key.ENTER
                # Enter repo name
                + "prefecthq/prefect"
                + readchar.key.ENTER
                +
                # Default image_name
                readchar.key.ENTER
                +
                # Default tag
                readchar.key.ENTER
                +
                # Reject push to registry
                "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Would you like to use the Dockerfile in the current directory?",
                "A Dockerfile exists. You chose not to use it.",
                "Image prefecthq/prefect/test-name:latest will be built",
                "Would you like to push this image to a remote registry?",
                "Would you like to save configuration for this deployment",
            ],
            expected_output_does_not_contain=["Is this a private registry?"],
        )

        assert result.exit_code == 0

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "test-name"
        assert config["deployments"][1]["build"] == [
            {
                "prefect_docker.deployments.steps.build_docker_image": {
                    "id": "build-image",
                    "requires": "prefect-docker>=0.3.1",
                    "dockerfile": "auto",
                    "image_name": "prefecthq/prefect/test-name",
                    "tag": "latest",
                }
            }
        ]

    async def test_prompt_build_custom_docker_image_accepted_use_existing_dockerfile_rejected_rename_rejected(
        self, docker_work_pool
    ):
        with open("Dockerfile", "w") as f:
            f.write("FROM python:3.9-slim\n")

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Reject use existing dockerfile
                + "n"
                + readchar.key.ENTER
                # Accept rename dockerfile
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=1,
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Would you like to use the Dockerfile in the current directory?",
                "A Dockerfile exists. You chose not to use it.",
                (
                    "A Dockerfile already exists. Please remove or rename the existing"
                    " one."
                ),
            ],
            expected_output_does_not_contain=["Is this a private registry?"],
        )

        assert result.exit_code == 1

    async def test_prompt_build_custom_docker_image_accepted_no_existing_dockerfile_uses_auto_build(
        self, docker_work_pool, monkeypatch, mock_build_docker_image
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Enter repo name
                + "prefecthq/prefect"
                + readchar.key.ENTER
                # Default image_name
                + readchar.key.ENTER
                # Default tag
                + readchar.key.ENTER
                # Reject push to registry
                + "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Image prefecthq/prefect/test-name:latest will be built",
                "Would you like to push this image to a remote registry?",
                "Would you like to save configuration for this deployment",
            ],
            expected_output_does_not_contain=["Is this a private registry?"],
        )

        assert result.exit_code == 0

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "test-name"
        assert config["deployments"][1]["build"] == [
            {
                "prefect_docker.deployments.steps.build_docker_image": {
                    "id": "build-image",
                    "requires": "prefect-docker>=0.3.1",
                    "dockerfile": "auto",
                    "image_name": "prefecthq/prefect/test-name",
                    "tag": "latest",
                }
            }
        ]

    async def test_no_existing_work_pool_image_gets_updated_after_adding_build_docker_image_step(
        self, docker_work_pool, monkeypatch, mock_build_docker_image
    ):
        prefect_file = Path("prefect.yaml")
        if prefect_file.exists():
            prefect_file.unlink()
        assert not prefect_file.exists()

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Enter repo name
                + "prefecthq/prefect"
                + readchar.key.ENTER
                # Default image_name
                + readchar.key.ENTER
                # Default tag
                + readchar.key.ENTER
                # Reject push to registry
                + "n"
                + readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Image prefecthq/prefect/test-name:latest will be built",
                "Would you like to push this image to a remote registry?",
                "Would you like to save configuration for this deployment",
            ],
            expected_output_does_not_contain=["Is this a private registry?"],
        )

        assert result.exit_code == 0

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 1
        assert config["deployments"][0]["name"] == "test-name"
        assert config["deployments"][0]["work_pool"]["name"] == docker_work_pool.name
        assert (
            config["deployments"][0]["work_pool"]["job_variables"]["image"]
            == "{{ build-image.image }}"
        )
        assert config["build"] == [
            {
                "prefect_docker.deployments.steps.build_docker_image": {
                    "id": "build-image",
                    "requires": "prefect-docker>=0.3.1",
                    "dockerfile": "auto",
                    "image_name": "prefecthq/prefect/test-name",
                    "tag": "latest",
                }
            }
        ]

    async def test_work_pool_image_already_exists_not_updated_after_adding_build_docker_image_step(
        self, docker_work_pool, monkeypatch, mock_build_docker_image
    ):
        prefect_file = Path("prefect.yaml")
        with open("prefect.yaml", "w") as f:
            contents = {
                "work_pool": {
                    "name": docker_work_pool.name,
                    "job_variables": {"image": "original-image"},
                }
            }
            yaml.dump(contents, f)
        assert prefect_file.exists()

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Enter repo name
                + "prefecthq/prefect"
                + readchar.key.ENTER
                # Default image_name
                + readchar.key.ENTER
                # Default tag
                + readchar.key.ENTER
                # Reject push to registry
                + "n"
                + readchar.key.ENTER
                # Decline remote storage
                + "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Image prefecthq/prefect/test-name:latest will be built",
                "Would you like to push this image to a remote registry?",
                "Would you like to save configuration for this deployment",
            ],
            expected_output_does_not_contain=["Is this a private registry?"],
        )

        assert result.exit_code == 0

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 1
        assert config["deployments"][0]["name"] == "test-name"
        assert config["deployments"][0]["work_pool"]["name"] == docker_work_pool.name
        assert (
            config["deployments"][0]["work_pool"]["job_variables"]["image"]
            == "{{ build-image.image }}"
        )
        assert config["work_pool"] == {
            "name": docker_work_pool.name,
            "job_variables": {"image": "original-image"},
        }

    async def test_deploying_managed_work_pool_does_not_prompt_to_build_image(
        self, managed_work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {managed_work_pool.name}"
            ),
            user_input=(
                # Decline remote storage
                "n"
                + readchar.key.ENTER
                # Decline save configuration
                + "n"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "$ prefect deployment run 'An important name/test-name'",
            ],
            expected_output_does_not_contain=[
                "Would you like to build a custom Docker image?",
            ],
        )


class TestDeployInfraOverrides:
    @pytest.fixture
    async def work_pool(self, prefect_client):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )

    async def test_uses_job_variables(self, project_dir, work_pool, prefect_client):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar --job-variable"
                ' \'{"resources":{"limits":{"cpu": 1}}}\''
            ),
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name",
                "prefect worker start --pool 'test-pool'",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"
        assert deployment.version == "1.0.0"
        assert deployment.tags == ["foo-bar"]
        assert deployment.job_variables == {
            "env": "prod",
            "resources": {"limits": {"cpu": 1}},
        }

    async def test_rejects_json_strings(self, project_dir, work_pool):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar --job-variable 'my-variable'"
            ),
            expected_code=1,
            expected_output_contains=[
                "Could not parse variable",
            ],
        )

    async def test_rejects_json_arrays(self, project_dir, work_pool):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar --job-variable ['my-variable']"
            ),
            expected_code=1,
            expected_output_contains=[
                "Could not parse variable",
            ],
        )

    async def test_rejects_invalid_json(self, project_dir, work_pool):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar --job-variable "
                ' \'{"resources":{"limits":{"cpu"}\''
            ),
            expected_code=1,
            expected_output_contains=[
                "Could not parse variable",
            ],
        )


@pytest.mark.usefixtures("project_dir", "interactive_console", "work_pool")
class TestDeployDockerPushSteps:
    async def test_prompt_push_custom_docker_image_rejected(
        self, docker_work_pool, monkeypatch, mock_build_docker_image
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Enter repo name
                + "prefecthq/prefect"
                + readchar.key.ENTER
                # Default image_name
                + readchar.key.ENTER
                # Default tag
                + readchar.key.ENTER
                # Reject push to registry
                + "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Image prefecthq/prefect/test-name:latest will be built",
                "Would you like to push this image to a remote registry?",
                "Would you like to save configuration for this deployment",
            ],
            expected_output_does_not_contain=["Is this a private registry?"],
        )

        assert result.exit_code == 0

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "test-name"
        assert config["deployments"][1]["build"] == [
            {
                "prefect_docker.deployments.steps.build_docker_image": {
                    "id": "build-image",
                    "requires": "prefect-docker>=0.3.1",
                    "dockerfile": "auto",
                    "image_name": "prefecthq/prefect/test-name",
                    "tag": "latest",
                }
            }
        ]
        assert not config["deployments"][1].get("push")

    async def test_prompt_push_custom_docker_image_accepted_public_registry(
        self, docker_work_pool, monkeypatch, mock_build_docker_image
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 3600"
                f" -p {docker_work_pool.name}"
            ),
            user_input=(
                # Accept build custom docker image
                "y"
                + readchar.key.ENTER
                # Enter repo name
                + "prefecthq/prefect"
                + readchar.key.ENTER
                # Default image_name
                + readchar.key.ENTER
                # Default tag
                + readchar.key.ENTER
                # Accept push to registry
                + "y"
                + readchar.key.ENTER
                # Registry URL
                + "https://hub.docker.com"
                + readchar.key.ENTER
                # Reject private registry
                + "n"
                + readchar.key.ENTER
                # Accept save configuration
                + "y"
                + readchar.key.ENTER
            ),
            expected_output_contains=[
                "Would you like to build a custom Docker image",
                "Image prefecthq/prefect/test-name:latest will be built",
                "Would you like to push this image to a remote registry?",
                "Is this a private registry?",
                "Would you like to save configuration for this deployment",
            ],
            expected_output_does_not_contain=[
                "Would you like use prefect-docker to manage Docker registry"
                " credentials?"
            ],
        )

        assert result.exit_code == 0

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][1]["name"] == "test-name"
        assert config["deployments"][1]["build"] == [
            {
                "prefect_docker.deployments.steps.build_docker_image": {
                    "id": "build-image",
                    "requires": "prefect-docker>=0.3.1",
                    "dockerfile": "auto",
                    "image_name": "https://hub.docker.com/prefecthq/prefect/test-name",
                    "tag": "latest",
                }
            }
        ]

        assert config["deployments"][1]["push"] == [
            {
                "prefect_docker.deployments.steps.push_docker_image": {
                    "requires": "prefect-docker>=0.3.1",
                    "image_name": "{{ build-image.image_name }}",
                    "tag": "{{ build-image.tag }}",
                }
            }
        ]


class TestDeployingUsingCustomPrefectFile:
    def customize_from_existing_prefect_file(
        self,
        existing_file: Path,
        new_file: io.TextIOBase,
        work_pool: Optional[WorkPool],
    ):
        with existing_file.open(mode="r") as f:
            contents = yaml.safe_load(f)

        # Customize the template
        contents["deployments"] = [
            {
                "name": "test-deployment1",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name if work_pool else "some_name"},
            },
            {
                "name": "test-deployment2",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {"name": work_pool.name if work_pool else "some_name"},
            },
        ]
        # Write the customized template
        yaml.dump(contents, new_file)

    @pytest.mark.usefixtures("project_dir")
    async def test_deploying_using_custom_prefect_file(
        self, prefect_client: PrefectClient, work_pool: WorkPool
    ):
        # Create and use a temporary prefect.yaml file
        with tempfile.NamedTemporaryFile("w+") as fp:
            self.customize_from_existing_prefect_file(
                Path("prefect.yaml"), fp, work_pool
            )

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=f"deploy --all --prefect-file {fp.name}",
                expected_code=0,
                user_input=(
                    # decline remote storage
                    "n"
                    + readchar.key.ENTER
                    # reject saving configuration
                    + "n"
                    + readchar.key.ENTER
                    # reject naming deployment
                    + "n"
                    + readchar.key.ENTER
                ),
                expected_output_contains=[
                    (
                        "Deployment 'An important name/test-deployment1' successfully"
                        " created"
                    ),
                    (
                        "Deployment 'An important name/test-deployment2' successfully"
                        " created"
                    ),
                ],
            )

        # Check if deployments were created correctly
        deployment1 = await prefect_client.read_deployment_by_name(
            "An important name/test-deployment1",
        )
        deployment2 = await prefect_client.read_deployment_by_name(
            "An important name/test-deployment2"
        )

        assert deployment1.name == "test-deployment1"
        assert deployment1.work_pool_name == work_pool.name
        assert deployment2.name == "test-deployment2"
        assert deployment2.work_pool_name == work_pool.name

    @pytest.mark.usefixtures("project_dir")
    async def test_deploying_using_missing_prefect_file(self):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all --prefect-file THIS_FILE_DOES_NOT_EXIST",
            expected_code=1,
            expected_output_contains=[
                "Unable to read the specified config file. Reason: [Errno 2] "
                "No such file or directory: 'THIS_FILE_DOES_NOT_EXIST'. Skipping"
            ],
        )

    @pytest.mark.usefixtures("project_dir")
    @pytest.mark.parametrize(
        "content", ["{this isn't valid YAML!}", "unbalanced blackets: ]["]
    )
    async def test_deploying_using_malformed_prefect_file(self, content: str):
        with tempfile.NamedTemporaryFile("w+") as fp:
            fp.write(content)

            await run_sync_in_worker_thread(
                invoke_and_assert,
                command=f"deploy --all --prefect-file {fp.name}",
                expected_code=1,
                expected_output_contains=[
                    "Unable to parse the specified config file. Skipping."
                ],
            )

    @pytest.mark.usefixtures("project_dir")
    async def test_deploying_directory_as_prefect_file(self):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all --prefect-file ./",
            expected_code=1,
            expected_output_contains=[
                "Unable to read the specified config file. Reason: [Errno 21] "
                "Is a directory: '.'. Skipping."
            ],
        )
