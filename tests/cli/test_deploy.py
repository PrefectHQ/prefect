import os
import shutil
import sys
from datetime import timedelta
from pathlib import Path

import pendulum
import pytest
import yaml

import prefect
from prefect.blocks.system import Secret
from prefect.exceptions import ObjectNotFound
from prefect.projects import register_flow
from prefect.projects.base import create_default_deployment_yaml, initialize_project
from prefect.server.schemas.actions import WorkPoolCreate
from prefect.server.schemas.schedules import CronSchedule
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

    async def test_project_deploy_with_no_deployment_file(
        self, project_dir, orion_client
    ):
        # delete deployment.yaml
        Path(project_dir, "deployment.yaml").unlink()

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

    async def test_project_deploy_with_empty_dep_file(self, project_dir, orion_client):
        # delete deployment.yaml and rewrite as empty
        Path(project_dir, "deployment.yaml").unlink()

        with open(Path(project_dir, "deployment.yaml"), "w") as f:
            f.write("{}")

        await orion_client.create_work_pool(
            WorkPoolCreate(name="test-pool", type="test")
        )
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


class TestMultiDeploy:
    async def test_deploy_all(self, project_dir, orion_client, work_pool):
        # Create multiple deployments
        deployments = {
            "deployments": [
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
        }

        # Save deployments to deployment.yaml
        with open("deployment.yaml", "w") as f:
            yaml.dump(deployments, f)

        # Deploy all
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            expected_output_contains=[
                "An important name/test-name-1",
                "An important name/test-name-2",
            ],
        )

        # Check if deployments were created correctly
        deployment1 = await orion_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        deployment2 = await orion_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name
        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name

    async def test_deploy_selected_deployments(
        self, project_dir, orion_client, work_pool
    ):
        create_default_deployment_yaml(".")
        # Create three deployments
        deployments = {
            "deployments": [
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
        }

        # Save deployments to deployment.yaml
        with open("deployment.yaml", "w") as f:
            yaml.dump(deployments, f)

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
            expected_output_does_not_contain=(
                "Deployment 'An important name/test-name-3' successfully created"
                " with id"
            ),
        )

        # Check if the two deployments were created correctly
        deployment1 = await orion_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        deployment2 = await orion_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name
        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name

        # Check if the third deployment was not created
        with pytest.raises(ObjectNotFound):
            await orion_client.read_deployment_by_name("An important name/test-name-3")

    async def test_deploy_single_with_cron_schedule(
        self, project_dir, orion_client, work_pool
    ):
        # Create multiple deployments
        deployments = {
            "deployments": [
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
        }

        # Save deployments to deployment.yaml
        with open("deployment.yaml", "w") as f:
            yaml.dump(deployments, f)

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
        deployment = await orion_client.read_deployment_by_name(
            "An important name/test-name-1"
        )

        assert deployment.name == "test-name-1"
        assert deployment.work_pool_name == work_pool.name
        assert deployment.schedule == CronSchedule(cron="0 * * * *")

        # Check if the second deployment was not created
        with pytest.raises(ObjectNotFound):
            await orion_client.read_deployment_by_name("An important name/test-name-2")

    @pytest.mark.parametrize(
        "deployment_selector_options", ["--all", "-n test-name-1 -n test-name-2"]
    )
    async def test_deploy_multiple_with_cli_options(
        self, project_dir, orion_client, work_pool, deployment_selector_options
    ):
        # Create multiple deployments
        deployments = {
            "deployments": [
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
        }

        # Save deployments to deployment.yaml
        with open("deployment.yaml", "w") as f:
            yaml.dump(deployments, f)

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
        deployment1 = await orion_client.read_deployment_by_name(
            "An important name/test-name-1"
        )
        deployment2 = await orion_client.read_deployment_by_name(
            "An important name/test-name-2"
        )

        assert deployment1.name == "test-name-1"
        assert deployment1.work_pool_name == work_pool.name
        assert deployment1.schedule is None

        assert deployment2.name == "test-name-2"
        assert deployment2.work_pool_name == work_pool.name
        assert deployment2.schedule is None

    async def test_deploy_with_invalid_name(self, project_dir, orion_client, work_pool):
        # Create a deployment
        deployment = {
            "deployments": [
                {
                    "entrypoint": "./flows/hello.py:my_flow",
                    "name": "test-name-1",
                    "work_pool": {"name": work_pool.name},
                }
            ]
        }

        # Save the deployment to deployment.yaml
        with open("deployment.yaml", "w") as f:
            yaml.dump(deployment, f)

        # Deploy the deployment with an invalid name
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --name invalid-name",
            expected_code=1,
            expected_output_contains=[
                "Deployment 'invalid-name' not found in deployment.yaml"
            ],
        )

        # Check if no deployments were created
        with pytest.raises(ObjectNotFound):
            await orion_client.read_deployment_by_name("An important name/test-name-1")

        with pytest.raises(ObjectNotFound):
            await orion_client.read_deployment_by_name("An important name/invalid-name")

    async def test_deploy_without_name_in_deployment_yaml(
        self, project_dir, orion_client, work_pool
    ):
        # Create multiple deployments with one missing a name
        deployments = {
            "deployments": [
                {
                    "entrypoint": "./flows/hello.py:my_flow",
                    "name": "test-name-1",
                    "work_pool": {"name": work_pool.name},
                },
                {
                    "entrypoint": "./flows/hello.py:my_flow",
                    # Missing name
                    "work_pool": {"name": work_pool.name},
                },
            ]
        }

        # Save deployments to deployment.yaml
        with open("deployment.yaml", "w") as f:
            yaml.dump(deployments, f)

        # Attempt to deploy all
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command="deploy --all",
            expected_code=0,
            expected_output_contains=[
                "Discovered deployment with no name. Skipping..."
            ],
        )

        with pytest.raises(ObjectNotFound):
            await orion_client.read_deployment_by_name("An important name/test-name-2")

    async def test_deploy_with_name_not_in_deployment_yaml(
        self, project_dir, orion_client, work_pool
    ):
        # Create multiple deployments with one missing a name
        deployments = {
            "deployments": [
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
        }

        # Save deployments to deployment.yaml
        with open("deployment.yaml", "w") as f:
            yaml.dump(deployments, f)

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

        deployment = await orion_client.read_deployment_by_name(
            "An important name/test-name-2"
        )
        assert deployment.name == "test-name-2"
        assert deployment.work_pool_name == work_pool.name

        with pytest.raises(ObjectNotFound):
            await orion_client.read_deployment_by_name("An important name/test-name-3")
