import os
import shutil
import sys
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pendulum
import pytest
import readchar
import yaml
from test_cloud import interactive_console  # noqa

import prefect
from prefect.blocks.system import Secret
from prefect.projects import register_flow
from prefect.projects.base import create_default_deployment_yaml, initialize_project
from prefect.server.schemas.actions import WorkPoolCreate
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


@pytest.fixture
def project_dir(tmp_path):
    original_dir = os.getcwd()
    if sys.version_info >= (3, 8):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        (tmp_path / ".prefect").mkdir(exist_ok=True)
        os.chdir(tmp_path)
        initialize_project()
        yield tmp_path
    else:
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path / "three-seven")
        (tmp_path / "three-seven" / ".prefect").mkdir(exist_ok=True)
        os.chdir(tmp_path / "three-seven")
        initialize_project()
        yield tmp_path / "three-seven"
    os.chdir(original_dir)


class TestProjectRecipes:
    def test_project_recipe_ls(self):
        result = invoke_and_assert("project recipe ls")
        assert result.exit_code == 0

        lines = result.output.split()
        assert len(lines) > 3
        assert "local" in lines
        assert "docker" in lines
        assert "git" in lines


class TestProjectInit:
    def test_project_init(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                "project init --name test_project", temp_dir=str(tempdir)
            )
            assert result.exit_code == 0
            for file in ["prefect.yaml", "deployment.yaml", ".prefectignore"]:
                # temp_dir creates a *new* nested temporary directory within tempdir
                assert any(Path(tempdir).rglob(file))

    def test_project_init_with_recipe(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                "project init --name test_project --recipe local", temp_dir=str(tempdir)
            )
            assert result.exit_code == 0

    @pytest.mark.usefixtures("interactive_console")
    def test_project_init_with_interactive_recipe(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                "project init --name test_project --recipe docker",
                expected_code=0,
                temp_dir=str(tempdir),
                user_input="my-image/foo"
                + readchar.key.ENTER
                + "testing"
                + readchar.key.ENTER,
                expected_output_contains=[
                    "image_name:",
                    "tag:",
                ],
            )
            prefect_file = list(Path(tempdir).rglob("prefect.yaml")).pop()
            with open(prefect_file, "r") as f:
                configuration = yaml.safe_load(f)

            assert (
                configuration["build"][0][
                    "prefect_docker.projects.steps.build_docker_image"
                ]["image_name"]
                == "my-image/foo"
            )
            assert (
                configuration["build"][0][
                    "prefect_docker.projects.steps.build_docker_image"
                ]["tag"]
                == "testing"
            )

    @pytest.mark.usefixtures("interactive_console")
    def test_project_init_with_partial_interactive_recipe(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                "project init --name test_project --recipe docker --field tag=my-tag",
                expected_code=0,
                temp_dir=str(tempdir),
                user_input="my-image/foo" + readchar.key.ENTER,
                expected_output_contains=[
                    "image_name:",
                ],
            )
            prefect_file = list(Path(tempdir).rglob("prefect.yaml")).pop()
            with open(prefect_file, "r") as f:
                configuration = yaml.safe_load(f)

            assert (
                configuration["build"][0][
                    "prefect_docker.projects.steps.build_docker_image"
                ]["image_name"]
                == "my-image/foo"
            )
            assert (
                configuration["build"][0][
                    "prefect_docker.projects.steps.build_docker_image"
                ]["tag"]
                == "my-tag"
            )

    def test_project_init_with_no_interactive_recipe(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                (
                    "project init --name test_project --recipe docker --field"
                    " tag=my-tag --field image_name=my-image/foo"
                ),
                expected_code=0,
                temp_dir=str(tempdir),
            )
            prefect_file = list(Path(tempdir).rglob("prefect.yaml")).pop()
            with open(prefect_file, "r") as f:
                configuration = yaml.safe_load(f)

            assert (
                configuration["build"][0][
                    "prefect_docker.projects.steps.build_docker_image"
                ]["image_name"]
                == "my-image/foo"
            )
            assert (
                configuration["build"][0][
                    "prefect_docker.projects.steps.build_docker_image"
                ]["tag"]
                == "my-tag"
            )

    def test_project_init_with_unknown_recipe(self):
        result = invoke_and_assert(
            "project init --name test_project --recipe def-not-a-recipe",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert "prefect project recipe ls" in result.output


class TestProjectDeploy:
    async def test_project_deploy(self, project_dir, orion_client):
        await orion_client.create_work_pool(
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

        deployment = await orion_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"
        assert deployment.version == "1.0.0"
        assert deployment.tags == ["foo-bar"]
        assert deployment.infra_overrides == {"env": "prod"}

    async def test_project_deploy_templates_values(self, project_dir, orion_client):
        await orion_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )

        # prepare a templated deployment
        with open("deployment.yaml", "r") as f:
            deployment = yaml.safe_load(f)

        deployment["version"] = "{{ input }}"
        deployment["tags"] = "{{ output2 }}"
        deployment["description"] = "{{ output1 }}"

        # save it back
        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(deployment, f)

        # update prefectl.yaml to include a new build step
        with open("prefect.yaml", "r") as f:
            prefect_config = yaml.safe_load(f)

        # test step that returns a dictionary of inputs and output1, output2
        prefect_config["build"] = [
            {"prefect.testing.utilities.a_test_step": {"input": "foo"}}
        ]

        # save it back
        with open("prefect.yaml", "w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name -p test-pool",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await orion_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.name == "test-name"
        assert deployment.work_pool_name == "test-pool"
        assert deployment.version == "foo"
        assert deployment.tags == ["b", "2", "3"]
        assert deployment.description == "1"

    async def test_project_deploy_templates_pull_step_safely(
        self, project_dir, orion_client
    ):
        "We want step outputs to get templated, but block references to only be retrieved at runtime"

        await Secret(value="super-secret-name").save(name="test-secret")
        await orion_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )

        # update prefectl.yaml to include a new build step
        with open("prefect.yaml", "r") as f:
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
        with open("prefect.yaml", "w") as f:
            yaml.safe_dump(prefect_config, f)

        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name -p test-pool",
        )
        assert result.exit_code == 0
        assert "An important name/test" in result.output

        deployment = await orion_client.read_deployment_by_name(
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
        self, project_dir, orion_client, work_pool
    ):
        await register_flow("flows/hello.py:my_flow")
        create_default_deployment_yaml(".")
        with open("deployment.yaml", "r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["flow_name"] = "An important name"
        deploy_config["work_pool"]["name"] = work_pool.name

        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

    async def test_project_deploy_reads_entrypoint_from_deployment_yaml(
        self, project_dir, orion_client, work_pool
    ):
        create_default_deployment_yaml(".")
        with open("deployment.yaml", "r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["entrypoint"] = "flows/hello.py:my_flow"
        deploy_config["work_pool"]["name"] = work_pool.name

        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=0,
            expected_output_contains="An important name/test-name",
        )

    async def test_project_deploy_exits_with_name_and_entrypoint_passed(
        self, project_dir, orion_client, work_pool
    ):
        create_default_deployment_yaml(".")
        with open("deployment.yaml", "r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["work_pool"]["name"] = work_pool.name

        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy -f 'An important name' flows/hello.py:my_flow",
            expected_code=1,
            expected_output="Can only pass an entrypoint or a flow name but not both.",
        )

    async def test_project_deploy_exits_with_no_name_or_entrypoint_configured(
        self, project_dir, orion_client, work_pool
    ):
        create_default_deployment_yaml(".")
        with open("deployment.yaml", "r") as f:
            deploy_config = yaml.safe_load(f)

        deploy_config["name"] = "test-name"
        deploy_config["work_pool"]["name"] = work_pool.name

        with open("deployment.yaml", "w") as f:
            yaml.safe_dump(deploy_config, f)

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy",
            expected_code=1,
            expected_output="An entrypoint or flow name must be provided.",
        )


class TestSchedules:
    async def test_passing_cron_schedules_to_deploy(self, project_dir, orion_client):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --cron '0 4 * * *'"
                " --timezone 'Europe/Berlin'"
            ),
        )
        assert result.exit_code == 0

        deployment = await orion_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedule.cron == "0 4 * * *"
        assert deployment.schedule.timezone == "Europe/Berlin"

    async def test_passing_interval_schedules_to_deploy(
        self, project_dir, orion_client
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --interval 42"
                " --anchor-date 2040-02-02 --timezone 'America/New_York'"
            ),
        )
        assert result.exit_code == 0

        deployment = await orion_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert deployment.schedule.interval == timedelta(seconds=42)
        assert deployment.schedule.anchor_date == pendulum.parse("2040-02-02")
        assert deployment.schedule.timezone == "America/New_York"

    async def test_passing_anchor_without_interval_exits(self, project_dir):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name --anchor-date 2040-02-02"
            ),
            expected_code=1,
            expected_output_contains=(
                "An anchor date can only be provided with an interval schedule"
            ),
        )

    async def test_parsing_rrule_schedule_string_literal(
        self, project_dir, orion_client
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command=(
                "deploy ./flows/hello.py:my_flow -n test-name "
                "--rrule"
                " 'DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17'"
            ),
            expected_code=0,
        )

        deployment = await orion_client.read_deployment_by_name(
            "An important name/test-name"
        )
        assert (
            deployment.schedule.rrule
            == "DTSTART:20220910T110000\nRRULE:FREQ=HOURLY;BYDAY=MO,TU,WE,TH,FR,SA;BYHOUR=9,10,11,12,13,14,15,16,17"
        )

    @pytest.mark.parametrize(
        "schedules",
        [
            ["--cron", "cron-str", "--interval", "42"],
            ["--rrule", "rrule-str", "--interval", "42"],
            ["--rrule", "rrule-str", "--cron", "cron-str"],
            ["--rrule", "rrule-str", "--cron", "cron-str", "--interval", "42"],
        ],
    )
    async def test_providing_multiple_schedules_exits_with_error(
        self, project_dir, schedules
    ):
        result = await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy ./flows/hello.py:my_flow -n test-name "
            + " ".join(schedules),
            expected_code=1,
            expected_output="Only one schedule type can be provided.",
        )
