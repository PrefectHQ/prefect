import os
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

import prefect
from prefect.projects.base import initialize_project
from prefect.server.schemas.actions import WorkPoolCreate
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread

TEST_PROJECTS_DIR = prefect.__root_path__ / "tests" / "test-projects"


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

    def test_project_init_with_unknown_recipe(self):
        result = invoke_and_assert(
            "project init --name test_project --recipe def-not-a-recipe",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert "prefect project recipe ls" in result.output


class TestProjectDeploy:
    async def test_project_deploy(self, project_dir, orion_client):
        await orion_client.create_work_pool(WorkPoolCreate(name="test-pool"))
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
        await orion_client.create_work_pool(WorkPoolCreate(name="test-pool"))

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
