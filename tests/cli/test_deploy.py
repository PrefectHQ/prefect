import datetime
import os
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from unittest import mock
from uuid import UUID, uuid4

import pendulum
from prefect.cli.deploy import (
    _check_for_matching_deployment_name_and_entrypoint_in_prefect_file,
)
import pytest
import readchar
from typer import Exit
import yaml

import prefect
from prefect.cli.deploy import (
    _initialize_deployment_triggers,
    _create_deployment_triggers,
)
from prefect.blocks.system import Secret
from prefect.client.orchestration import PrefectClient, ServerType
from prefect.events.schemas import Posture
from prefect.exceptions import ObjectNotFound
from prefect.deployments import register_flow
from prefect.deployments.base import (
    _save_deployment_to_prefect_file,
    create_default_prefect_yaml,
    initialize_project,
)
from prefect.server.schemas.actions import WorkPoolCreate
from prefect.server.schemas.schedules import CronSchedule
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread


TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


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
    original_dir = os.getcwd()
    if sys.version_info >= (3, 8):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        os.chdir(tmp_path)
        initialize_project()
        yield tmp_path
    else:
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path / "three-seven")
        prefect_home = tmp_path / "three-seven" / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        os.chdir(tmp_path / "three-seven")
        initialize_project()
        yield tmp_path / "three-seven"
    os.chdir(original_dir)


@pytest.fixture
def project_dir_with_single_deployment_format(tmp_path):
    original_dir = os.getcwd()
    if sys.version_info >= (3, 8):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        os.chdir(tmp_path)
        initialize_project()

        with open("prefect.yaml", "r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"][0]["schedule"] = None

        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(contents["deployments"][0], f)

        yield tmp_path
    else:
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path / "three-seven")
        (tmp_path / "three-seven" / ".prefect").mkdir(exist_ok=True, mode=0o0700)
        os.chdir(tmp_path / "three-seven")
        initialize_project()

        with open("prefect.yaml", "r") as f:
            contents = yaml.safe_load(f)

        contents["deployments"][0]["schedule"] = None

        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(contents["deployments"][0], f)

        yield tmp_path / "three-seven"
    os.chdir(original_dir)


@pytest.fixture
async def default_agent_pool(prefect_client):
    return await prefect_client.create_work_pool(
        WorkPoolCreate(name="default-agent-pool", type="prefect-agent")
    )


class TestProjectDeploySingleDeploymentYAML:
    """
    Tests for projects where deployment.yaml contains only one deployment
    definition.
    """

    async def test_project_deploy(
        self, project_dir_with_single_deployment_format, prefect_client
    ):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar"
            ),
            expected_code=0,
            # check for deprecation message
            expected_output_contains=[
                "An important name/test-name",
                "Using a `deployment.yaml` file with `prefect deploy`",
                (
                    "Please use the `prefect.yaml` file instead by copying the"
                    " contents of your `deployment.yaml` file into your `prefect.yaml`"
                    " file."
                ),
            ],
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
        assert deployment.infra_overrides == {"env": "prod"}

    async def test_project_deploy_with_no_deployment_file(
        self, project_dir, prefect_client
    ):
        # delete deployment.yaml

        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar"
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
        assert deployment.infra_overrides == {"env": "prod"}

    async def test_project_deploy_with_empty_dep_file(
        self, project_dir_with_single_deployment_format, prefect_client
    ):
        # delete deployment.yaml and rewrite as empty
        deployment_file = Path(
            project_dir_with_single_deployment_format, "deployment.yaml"
        )
        deployment_file.unlink()

        with deployment_file.open(mode="w") as f:
            f.write("{}")

        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name -p test-pool",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"

    async def test_project_deploy_templates_values(
        self, project_dir_with_single_deployment_format, prefect_client
    ):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )

        # prepare a templated deployment
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deployment = yaml.safe_load(f)

        deployment["version"] = "{{ input }}"
        deployment["tags"] = "{{ output2 }}"
        deployment["description"] = "{{ output1 }}"

        # save it back
        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deployment, f)

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

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name -p test-pool",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"
        assert deployment.version == "foo"
        assert deployment.tags == ["b", "2", "3"]
        assert deployment.description == "1"

    async def test_project_deploy_with_default_parameters(
        self, project_dir_with_single_deployment_format, prefect_client, work_pool
    ):
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["parameters"] = {"number": 1, "message": "hello"}
        deploy_config["name"] = "test-name"
        deploy_config["entrypoint"] = "flows/hello.py:my_flow"
        deploy_config["work_pool"]["name"] = work_pool.name

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
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
        self,
        project_dir_with_single_deployment_format,
        prefect_client,
        work_pool,
        option,
    ):
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["parameters"] = {"number": 1, "message": "hello"}
        deploy_config["name"] = "test-name"
        deploy_config["entrypoint"] = "flows/hello.py:my_flow"
        deploy_config["work_pool"]["name"] = work_pool.name

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy {option}",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.parameters == {"number": 2, "message": "hello"}

    async def test_project_deploy_templates_pull_step_safely(
        self, project_dir_with_single_deployment_format, prefect_client
    ):
        """
        We want step outputs to get templated, but block references to only be
        retrieved at runtime
        """

        await Secret(value="super-secret-name").save(name="test-secret")
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )

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
                "prefect.testing.utilities.a_test_step": {
                    "input": "{{ output1 }}",
                    "secret-input": "{{ prefect.blocks.secret.test-secret }}",
                }
            },
        ]
        # save it back
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name -p test-pool",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.pull_steps == [
            {
                "prefect.testing.utilities.a_test_step": {
                    "input": 1,
                    "secret-input": "{{ prefect.blocks.secret.test-secret }}",
                }
            }
        ]

    async def test_project_deploy_reads_flow_name_from_deployment_yaml(
        self, project_dir_with_single_deployment_format, prefect_client, work_pool
    ):
        await register_flow("flows/hello.py:my_flow")
        deploy_config = {
            "name": "test-name",
            "flow_name": "An important name",
            "work_pool": {"name": work_pool.name},
        }

        with Path("deployment.yaml").open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

    async def test_project_deploy_reads_entrypoint_from_deployment_yaml(
        self, project_dir_with_single_deployment_format, prefect_client, work_pool
    ):
        create_default_prefect_yaml(".")
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["entrypoint"] = "flows/hello.py:my_flow"
        deploy_config["work_pool"]["name"] = work_pool.name

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

    async def test_project_deploy_exits_with_name_and_entrypoint_passed(
        self, project_dir_with_single_deployment_format, prefect_client, work_pool
    ):
        create_default_prefect_yaml(".")
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["work_pool"]["name"] = work_pool.name

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -f 'An important name' flows/hello.py:my_flow",
            expected_code=1,
            expected_output_contains=[
                "Received an entrypoint and a flow name for this deployment. Please"
                " provide either an entrypoint or a flow name."
            ],
        )

    async def test_project_deploy_exits_with_no_name_or_entrypoint_configured(
        self, project_dir_with_single_deployment_format, prefect_client, work_pool
    ):
        create_default_prefect_yaml(".")
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["work_pool"]["name"] = work_pool.name

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=1,
            expected_output_contains="An entrypoint or flow name must be provided.",
        )

    @pytest.mark.usefixtures(
        "project_dir_with_single_deployment_format", "interactive_console"
    )
    async def test_migrate_from_deployment_yaml_to_prefect_yaml(self, work_pool):
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["entrypoint"] = "flows/hello.py:my_flow"
        deploy_config["work_pool"]["name"] = work_pool.name
        deploy_config["schedule"] = {"interval": 3600}

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            user_input="y"
            + readchar.key.ENTER
            + readchar.key.ENTER
            + "n"
            + readchar.key.ENTER,
            expected_code=0,
        )

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 1
        assert config["deployments"][0]["name"] == "test-name"
        assert config["deployments"][0]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][0]["schedule"] == {"interval": 3600}
        assert config["deployments"][0]["work_pool"]["name"] == work_pool.name


class TestProjectDeploy:
    async def test_project_deploy(self, project_dir, prefect_client):
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
        assert deployment.infra_overrides == {"env": "prod"}

    async def test_project_deploy_with_no_deployment_file(
        self, project_dir, prefect_client
    ):
        await prefect_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name -p test-pool --version"
                " 1.0.0 -v env=prod -t foo-bar"
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
        assert deployment.infra_overrides == {"env": "prod"}

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
                "$ prefect project recipes ls",
            ],
        )

    class TestGeneratedPullAction:
        @pytest.fixture
        def uninitialized_project_dir(self, project_dir):
            Path(project_dir, "prefect.yaml").unlink()
            return project_dir

        @pytest.fixture
        def uninitialized_project_dir_with_git_no_remote(
            self, uninitialized_project_dir
        ):
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
                    # Accept pulling from remote git origin
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
                    "Would you like your workers to pull your flow code from its remote"
                    " repository when running this flow?"
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
                    # Accept pulling from remote git origin
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
                    "Would you like your workers to pull your flow code from its remote"
                    " repository when running this flow?"
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
            "interactive_console", "uninitialized_project_dir_with_git_with_remote"
        )
        async def test_project_deploy_with_no_prefect_yaml_git_repo_with_token(
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
                    # Accept pulling from remote git origin
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
                    "Would you like your workers to pull your flow code from its remote"
                    " repository when running this flow?"
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

    async def test_project_deploy_with_empty_dep_file(
        self, project_dir, prefect_client, work_pool
    ):
        deployment_file = project_dir / "deployment.yaml"
        with deployment_file.open(mode="w") as f:
            f.write("{}")

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name -p {work_pool.name}",
            expected_code=0,
            expected_output_contains=["An important name/test"],
        )
        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-work-pool"

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

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=f"deploy ./flows/hello.py:my_flow -n test-name -p {work_pool.name}",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-work-pool"
        assert deployment.version == "foo"
        assert deployment.tags == ["b", "2", "3"]
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
    async def test_project_deploy_reads_flow_name_from_prefect_yaml(self, work_pool):
        await register_flow("flows/hello.py:my_flow")
        create_default_prefect_yaml(".")
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["flow_name"] = "An important name"
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
    async def test_project_deploy_exits_with_name_and_entrypoint_passed(
        self, work_pool
    ):
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"][0]["name"] = "test-name"
        deploy_config["deployments"][0]["work_pool"]["name"] = work_pool.name

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -f 'An important name' -n test-name flows/hello.py:my_flow",
            expected_code=1,
            expected_output=(
                "Received an entrypoint and a flow name for this deployment. Please"
                " provide either an entrypoint or a flow name."
            ),
        )

    @pytest.mark.usefixtures("project_dir")
    async def test_project_deploy_exits_with_no_name_or_entrypoint_configured(
        self, work_pool
    ):
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
            expected_output_contains="An entrypoint or flow name must be provided.",
        )

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_without_name_interactive(self, work_pool, prefect_client):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                f"deploy ./flows/hello.py:my_flow -p {work_pool.name} --interval 3600"
            ),
            expected_code=0,
            user_input="test-prompt-name"
            + readchar.key.ENTER
            + "n"
            + readchar.key.ENTER,
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
            user_input=readchar.key.ENTER + "n" + readchar.key.ENTER,
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
            user_input=readchar.key.ENTER + "n" + readchar.key.ENTER,
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
    async def test_deploy_with_no_available_work_pool_interactive(
        self, prefect_client, default_agent_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name --interval 3600",
            expected_code=0,
            user_input=(
                # Accept creating a new work pool
                readchar.key.ENTER
                +
                # Select the first work pool type
                readchar.key.ENTER
                +
                # Enter a name for the new work pool
                "test-created-via-deploy"
                + readchar.key.ENTER
                # Decline save
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

    async def test_project_deploy_with_flow_name_generate_deprecation_warning(
        self, project_dir_with_single_deployment_format, prefect_client, work_pool
    ):
        await register_flow("flows/hello.py:my_flow")
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["flow_name"] = "An important name"
        deploy_config["work_pool"]["name"] = work_pool.name

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=0,
            expected_output_contains=(
                "The ability to deploy by flow name has been deprecated"
            ),
        )

    async def test_project_deploy_with_explicit_flow_name_flag_generates_deprecation_warning(
        self, project_dir_with_single_deployment_format, prefect_client, work_pool
    ):
        await register_flow("flows/hello.py:my_flow")
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["flow_name"] = "An important name"
        deploy_config["work_pool"]["name"] = work_pool.name

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -f 'An important name'",
            expected_code=0,
            expected_output_contains=(
                "The ability to deploy by flow name has been deprecated"
            ),
        )

    @pytest.mark.usefixtures(
        "project_dir_with_single_deployment_format", "interactive_console"
    )
    async def test_migrate_from_deployment_yaml_to_prefect_yaml(self, work_pool):
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"] = [
            {
                "name": "test-name",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {
                    "name": work_pool.name,
                },
                "schedule": {
                    "interval": 3600,
                },
            }
        ]

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            user_input=(
                # accept migration
                "y"
                + readchar.key.ENTER
                +
                # choose existing deployment configuration
                readchar.key.ENTER
                +
                # accept save
                "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Successfully copied your deployment configurations into your"
                " prefect.yaml file! Once you've verified that all your deployment"
                " configurations in your prefect.yaml file are correct, you can delete"
                " your deployment.yaml file."
            ],
        )

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 1
        assert config["deployments"][0]["name"] == "test-name"
        assert config["deployments"][0]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][0]["schedule"] == {"interval": 3600}
        assert config["deployments"][0]["work_pool"]["name"] == work_pool.name

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
    async def test_deploy_does_not_prompt_when_empty_schedule_prefect_yaml(
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
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedule is None


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
        assert deployment.schedule.cron == "0 4 * * *"
        assert deployment.schedule.timezone == "Europe/Berlin"

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
        assert deployment.schedule.cron == "0 4 * * *"
        assert deployment.schedule.timezone == "America/Chicago"

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
        assert deployment.schedule.cron == "0 4 * * *"
        assert deployment.schedule.timezone == "Europe/Berlin"

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
        assert deployment.schedule.interval == timedelta(seconds=42)
        assert deployment.schedule.anchor_date == pendulum.parse("2040-02-02")
        assert deployment.schedule.timezone == "America/New_York"

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
        assert deployment.schedule.interval == timedelta(seconds=42)
        assert deployment.schedule.anchor_date == pendulum.parse("2040-02-02")
        assert deployment.schedule.timezone == "America/Chicago"

    @pytest.mark.usefixtures("project_dir")
    async def test_passing_anchor_without_interval_exits(self):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --anchor-date 2040-02-02"
            ),
            expected_code=1,
            expected_output_contains=(
                "An anchor date can only be provided with an interval schedule"
            ),
        )

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
        assert (
            deployment.schedule.rrule
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
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )

    @pytest.mark.usefixtures("project_dir")
    @pytest.mark.parametrize(
        "schedules",
        [
            ["--cron", "cron-str", "--interval", "42"],
            ["--rrule", "rrule-str", "--interval", "42"],
            ["--rrule", "rrule-str", "--cron", "cron-str"],
            ["--rrule", "rrule-str", "--cron", "cron-str", "--interval", "42"],
        ],
    )
    async def test_providing_multiple_schedules_exits_with_error(self, schedules):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name "
            + " ".join(schedules),
            expected_code=1,
            expected_output_contains=["Only one schedule type can be provided."],
        )

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
                +
                # Select interval schedule
                readchar.key.ENTER
                +
                # Enter invalid interval
                "bad interval"
                + readchar.key.ENTER
                +
                # Enter another invalid interval
                "0"
                + readchar.key.ENTER
                +
                # Enter valid interval
                "42"
                + readchar.key.ENTER
                # Decline save
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
        assert deployment.schedule.interval == timedelta(seconds=42)

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
                +
                # Select cron schedule
                readchar.key.DOWN
                + readchar.key.ENTER
                +
                # Enter invalid cron string
                "bad cron string"
                + readchar.key.ENTER
                +
                # Enter cron
                "* * * * *"
                + readchar.key.ENTER
                +
                # Enter invalid timezone
                "bad timezone"
                + readchar.key.ENTER
                +
                # Select default timezone
                readchar.key.ENTER
                +
                # Decline save
                "n"
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
        assert deployment.schedule.cron == "* * * * *"

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
                +
                # Select rrule schedule
                readchar.key.DOWN
                + readchar.key.DOWN
                + readchar.key.ENTER
                +
                # Enter invalid rrule string
                "bad rrule string"
                + readchar.key.ENTER
                +
                # Enter valid rrule string
                "FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=20240730T040000Z"
                + readchar.key.ENTER
                # Enter invalid timezone
                + "bad timezone"
                + readchar.key.ENTER
                +
                # Select default timezone
                readchar.key.ENTER
                +
                # Decline save
                "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert (
            deployment.schedule.rrule
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
                # Decline save
                + "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedule is None

    @pytest.mark.usefixtures("interactive_console", "project_dir")
    async def test_deploy_no_schedule_interactive_with_ci_flag(
        self, prefect_client, work_pool
    ):
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --pool"
                f" {work_pool.name} --ci"
            ),
            expected_code=0,
            expected_output_contains=(
                "The `--ci` flag has been deprecated. It will not be available after"
                " Dec 2023. Please use the global `--no-prompt` flag instead: `prefect"
                " --no-prompt deploy`."
            ),
        )

        deployment = await prefect_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedule is None


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
        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name

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
        assert deployment.schedule == CronSchedule(cron="0 * * * *")

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
        assert deployment1.schedule is None

        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name
        assert deployment2.schedule is None

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
            user_input="y" + readchar.key.ENTER + "test-name-2" + readchar.key.ENTER,
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
            user_input="n" + readchar.key.ENTER,
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
                "An entrypoint or flow name must be provided.",
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
        assert deployment.infra_overrides == {"env": "prod"}

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

    async def test_deploy_with_single_deployment_with_no_name(
        self, project_dir, work_pool
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
            command="deploy -n test-name-1",
            expected_code=1,
            expected_output_contains=[
                (
                    "Could not find any deployment configurations with the given"
                    " name(s): test-name-1. Your flow will be deployed with a new"
                    " deployment configuration."
                ),
            ],
        )

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
            user_input=readchar.key.ENTER + "n" + readchar.key.ENTER,
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

    @pytest.mark.usefixtures(
        "project_dir_with_single_deployment_format", "interactive_console"
    )
    async def test_migrate_from_deployment_yaml_to_prefect_yaml(self, work_pool):
        deployment_file = Path("deployment.yaml")
        with deployment_file.open(mode="r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["deployments"] = [
            {
                "name": "test-name-1",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {
                    "name": work_pool.name,
                },
                "schedule": {
                    "interval": 3600,
                },
            },
            {
                "name": "test-name-2",
                "entrypoint": "flows/hello.py:my_flow",
                "work_pool": {
                    "name": work_pool.name,
                },
                "schedule": {
                    "interval": 3600,
                },
            },
        ]

        with deployment_file.open(mode="w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -n test-name-1",
            # accept migration
            user_input="y" + readchar.key.ENTER,
            expected_code=0,
            expected_output_contains=[
                "Successfully copied your deployment configurations into your"
                " prefect.yaml file! Once you've verified that all your deployment"
                " configurations in your prefect.yaml file are correct, you can delete"
                " your deployment.yaml file."
            ],
        )

        with open("prefect.yaml", "r") as f:
            config = yaml.safe_load(f)

        assert len(config["deployments"]) == 2
        assert config["deployments"][0]["name"] == "test-name-1"
        assert config["deployments"][0]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][0]["schedule"] == {"interval": 3600}
        assert config["deployments"][0]["work_pool"]["name"] == work_pool.name
        assert config["deployments"][1]["name"] == "test-name-2"
        assert config["deployments"][1]["entrypoint"] == "flows/hello.py:my_flow"
        assert config["deployments"][1]["schedule"] == {"interval": 3600}
        assert config["deployments"][1]["work_pool"]["name"] == work_pool.name


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
                +
                # accept save user inputs
                "y"
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
        assert config["deployments"][0]["schedule"] is None
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
                +
                # accept save user inputs
                "y"
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
        assert config["deployments"][1]["schedule"] is None
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

    def test_save_user_inputs_with_interval_schedule(self):
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # Accept default deployment name
                readchar.key.ENTER
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
                +
                # accept save user inputs
                "y"
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
        assert config["deployments"][1]["schedule"]["interval"] == 3600
        assert config["deployments"][1]["schedule"]["timezone"] == "UTC"
        assert config["deployments"][1]["schedule"]["anchor_date"] is not None

    def test_save_user_inputs_with_cron_schedule(self):
        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # Accept default deployment name
                readchar.key.ENTER
                +
                # accept schedule
                readchar.key.ENTER
                +
                # select cron schedule
                readchar.key.DOWN
                + readchar.key.ENTER
                +
                # enter cron schedule
                "* * * * *"
                + readchar.key.ENTER
                +
                # accept default timezone
                readchar.key.ENTER
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
                +
                # accept save user inputs
                "y"
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
        assert config["deployments"][1]["schedule"]["cron"] == "* * * * *"
        assert config["deployments"][1]["schedule"]["timezone"] == "UTC"
        assert config["deployments"][1]["schedule"]["day_or"]

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
                +
                # accept default timezone
                readchar.key.ENTER
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
                +
                # accept save user inputs
                "y"
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
        assert config["deployments"][1]["schedule"]["rrule"] == "FREQ=MINUTELY"
        assert config["deployments"][1]["schedule"]["timezone"] == "UTC"

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
                    "path": "/path/to/working/directory"
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

    def test_save_deployment_with_existing_deployment(self):
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
            config["deployments"][1]["work_pool"]["name"]
            == new_deployment["work_pool"]["name"]
        )

    def test_save_user_inputs_overwrite_confirmed(self):
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
                +
                # accept save user inputs
                "y"
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
        assert config["deployments"][1]["schedule"] is None
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
                +
                # accept save user inputs
                "y"
                + readchar.key.ENTER
                +
                # accept overwriting existing deployment that is found
                "y"
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
        assert config["deployments"][1]["schedule"]["interval"] == 3600
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
                +
                # accept save user inputs
                "y"
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
        assert config["deployments"][1]["schedule"] is None
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"

        invoke_and_assert(
            command="deploy flows/hello.py:my_flow",
            user_input=(
                # configure new deployment
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
                +
                # accept save user inputs
                "y"
                + readchar.key.ENTER
                +
                # reject overwriting existing deployment that is found
                "n"
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
        assert config["deployments"][1]["schedule"] is None
        assert config["deployments"][1]["work_pool"]["name"] == "inflatable"


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

    async def test_deploy_without_entrypoint_no_flows_found(
        self, prefect_client: PrefectClient
    ):
        Path("test_nested_folder").mkdir()
        os.chdir("test_nested_folder")
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            user_input=(
                # Enter valid entrypoint from sibling directory
                "../flows/hello.py:my_flow"
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
                # decline save user inputs
                "n"
                + readchar.key.ENTER
            ),
            expected_code=0,
            expected_output_contains=[
                "Flow entrypoint (expected format path/to/file.py:function_name)",
                "Deployment 'An important name/default' successfully created",
            ],
        )

        deployment = await prefect_client.read_deployment_by_name(
            name="An important name/default"
        )
        assert deployment.entrypoint == "../flows/hello.py:my_flow"


class TestCheckForMatchingDeployment:
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

        assert len(config["deployments"]) == 1

        assert config["deployments"][0]["name"] == deployment["name"]
        assert config["deployments"][0]["entrypoint"] == deployment["entrypoint"]

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

        assert len(config["deployments"]) == 1

        assert config["deployments"][0]["name"] == deployment["name"]
        assert config["deployments"][0]["entrypoint"] == deployment["entrypoint"]

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
            "entrypoint": "flows/existing_flow.py:my_flow",
        }
        matching_deployment_exists_2 = (
            _check_for_matching_deployment_name_and_entrypoint_in_prefect_file(
                deployment_with_same_name_but_different_entrypoint
            )
        )
        assert not matching_deployment_exists_2


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
        }

        triggers = _initialize_deployment_triggers("my_deployment", [trigger_spec])
        assert triggers == [
            {
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
                "within": datetime.timedelta(0),
                "parameters": None,
            }
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
        }

        triggers = _initialize_deployment_triggers("my_deployment", [trigger_spec])
        deployment_id = uuid4()

        await _create_deployment_triggers(client, deployment_id, triggers)

        assert triggers[0]._deployment_id == deployment_id
        client.delete_resource_owned_automations.assert_called_once_with(
            f"prefect.deployment.{deployment_id}"
        )
        client.create_automation.assert_called_once_with(triggers[0].as_automation())

    async def test_create_deployment_triggers_not_cloud_noop(self):
        client = AsyncMock()
        client.server_type = ServerType.SERVER

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
        deployment_id = uuid4()

        await _create_deployment_triggers(client, deployment_id, triggers)

        client.delete_resource_owned_automations.assert_not_called()
        client.create_automation.assert_not_called()

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

    async def test_deploy_command_warns_triggers_not_created_not_cloud(
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
                    }
                ],
            }
        ]

        with prefect_file.open(mode="w") as f:
            yaml.safe_dump(contents, f)

        # Deploy the deployment with a name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name-1",
            expected_code=0,
            expected_output_contains=[
                "Deployment triggers are only supported on Prefect Cloud"
            ],
        )
