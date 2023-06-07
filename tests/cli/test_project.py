from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import readchar
import yaml
from prefect.server import models
from prefect.client import schemas
from test_cloud import interactive_console  # noqa

from prefect.testing.cli import invoke_and_assert


@pytest.fixture
async def deployment_with_pull_step(
    session,
    flow,
):
    def hello(name: str):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.objects.Deployment(
            name="hello",
            flow_id=flow.id,
            pull_steps=[
                {"prefect.projects.steps.set_working_directory": {"directory": "/tmp"}},
            ],
        ),
    )
    await session.commit()

    return deployment


@pytest.fixture
async def deployment_with_pull_steps(
    session,
    flow,
):
    def hello(name: str):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.objects.Deployment(
            name="hello",
            flow_id=flow.id,
            pull_steps=[
                {
                    "prefect.projects.steps.set_working_directory": {
                        "directory": "/tmp"
                    },
                },
                {
                    "prefect.projects.steps.set_working_directory": {
                        "directory": "/private"
                    }
                },
            ],
        ),
    )
    await session.commit()

    return deployment


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
            invoke_and_assert(
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
            invoke_and_assert(
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
            invoke_and_assert(
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

            deployment_file = list(Path(tempdir).rglob("deployment.yaml")).pop()
            with open(deployment_file, "r") as f:
                deploy_config = yaml.safe_load(f)

            assert (
                deploy_config["deployments"][0]["work_pool"]["job_variables"]["image"]
                == "{{ image_name }}"
            )

    def test_project_init_with_unknown_recipe(self):
        result = invoke_and_assert(
            "project init --name test_project --recipe def-not-a-recipe",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert "prefect project recipe ls" in result.output


class TestProjectClone:
    def test_clone_with_no_options(self):
        result = invoke_and_assert(
            "project clone",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert "Must pass either a deployment name or deployment ID." in result.output

    def test_clone_with_both_name_and_id(self):
        result = invoke_and_assert(
            "project clone --deployment test_deployment --id 123",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert (
            "Can only pass one of deployment name or deployment ID options."
            in result.output
        )

    def test_clone_with_name_and_no_pull_steps(self, flow, deployment):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                f"project clone --deployment '{flow.name}/{deployment.name}'",
                temp_dir=str(tempdir),
                expected_code=1,
            )
            assert result.exit_code == 1
            assert "No pull steps found, exiting early." in result.output

    def test_clone_with_id_and_no_pull_steps(self, deployment):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                f"project clone --id {deployment.id}",
                temp_dir=str(tempdir),
                expected_code=1,
            )
            assert result.exit_code == 1
            assert "No pull steps found, exiting early." in result.output

    def test_clone_with_name_and_pull_step(self, flow, deployment_with_pull_step):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                (
                    "project clone --deployment"
                    f" {flow.name}/{deployment_with_pull_step.name}"
                ),
                temp_dir=str(tempdir),
                expected_code=0,
                expected_output_contains="/tmp",
            )
            assert result.exit_code == 0

    def test_clone_with_id_and_pull_steps(self, deployment_with_pull_steps):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                f"project clone --id {deployment_with_pull_steps.id}",
                temp_dir=str(tempdir),
                expected_code=0,
                expected_output_contains="/private",
            )
            assert result.exit_code == 0
