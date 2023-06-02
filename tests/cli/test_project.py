from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import readchar
import yaml
from test_cloud import interactive_console  # noqa

from prefect.testing.cli import invoke_and_assert


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
                user_input=f"my-image/foo{readchar.key.ENTER}",
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
