import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest
import readchar
import yaml
from typer import Exit

from prefect.client import schemas
from prefect.server import models
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock


@pytest.fixture
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.project.is_interactive", lambda: True)

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
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/PrefectHQ/hello-projects.git"
                    }
                },
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
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/PrefectHQ/hello-projects.git"
                    }
                },
                {
                    "prefect.deployments.steps.git_clone": {
                        "repository": "https://github.com/PrefectHQ/marvin.git"
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
                "init --name test_project", temp_dir=str(tempdir)
            )
            assert result.exit_code == 0
            for file in ["prefect.yaml", ".prefectignore"]:
                # temp_dir creates a *new* nested temporary directory within tempdir
                assert any(Path(tempdir).rglob(file))

    def test_project_init_with_recipe(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                "init --name test_project --recipe local",
                temp_dir=str(tempdir),
            )
            assert result.exit_code == 0

    @pytest.mark.usefixtures("interactive_console")
    def test_project_init_with_interactive_recipe(self):
        with TemporaryDirectory() as tempdir:
            invoke_and_assert(
                "init --name test_project --recipe docker",
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
                    "prefect_docker.deployments.steps.build_docker_image"
                ]["image_name"]
                == "my-image/foo"
            )
            assert (
                configuration["build"][0][
                    "prefect_docker.deployments.steps.build_docker_image"
                ]["tag"]
                == "testing"
            )

    @pytest.mark.usefixtures("interactive_console")
    def test_project_init_with_partial_interactive_recipe(self):
        with TemporaryDirectory() as tempdir:
            invoke_and_assert(
                "init --name test_project --recipe docker --field tag=my-tag",
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
                    "prefect_docker.deployments.steps.build_docker_image"
                ]["image_name"]
                == "my-image/foo"
            )
            assert (
                configuration["build"][0][
                    "prefect_docker.deployments.steps.build_docker_image"
                ]["tag"]
                == "my-tag"
            )

    def test_project_init_with_no_interactive_recipe(self):
        with TemporaryDirectory() as tempdir:
            invoke_and_assert(
                (
                    "init --name test_project --recipe docker --field"
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
                    "prefect_docker.deployments.steps.build_docker_image"
                ]["image_name"]
                == "my-image/foo"
            )
            assert (
                configuration["build"][0][
                    "prefect_docker.deployments.steps.build_docker_image"
                ]["tag"]
                == "my-tag"
            )

            assert (
                configuration["deployments"][0]["work_pool"]["job_variables"]["image"]
                == "{{ build_image.image }}"
            )

    def test_project_init_with_unknown_recipe(self):
        result = invoke_and_assert(
            "init --name test_project --recipe def-not-a-recipe",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert "prefect init" in result.output

    @pytest.mark.usefixtures("interactive_console")
    def test_project_init_opt_out_of_recipe(self):
        with TemporaryDirectory() as tempdir:
            result = invoke_and_assert(
                "init --name test_project",
                temp_dir=str(tempdir),
                user_input=(readchar.key.DOWN * 10) + readchar.key.ENTER,
            )
            assert result.exit_code == 0
            assert any(Path(tempdir).rglob("prefect.yaml"))


@pytest.fixture
def git_repository_mock(monkeypatch):
    pull_code_mock = AsyncMock()

    def init_git_repo(**kwargs):
        global name
        repository = kwargs.get("url")
        name = repository.split("/")[-1].split(".")[0].replace(".git", "")
        mock = MagicMock()
        mock.destination = Path.cwd() / name
        mock.pull_code = pull_code_mock
        return mock

    git_repository_mock = MagicMock()
    git_repository_mock.side_effect = init_git_repo
    monkeypatch.setattr(
        "prefect.deployments.steps.pull.GitRepository",
        git_repository_mock,
    )
    return git_repository_mock


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
        result = invoke_and_assert(
            f"project clone --deployment '{flow.name}/{deployment.name}'",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert "No pull steps found, exiting early." in result.output

    def test_clone_with_id_and_no_pull_steps(self, deployment):
        result = invoke_and_assert(
            f"project clone --id {deployment.id}",
            expected_code=1,
        )
        assert result.exit_code == 1
        assert "No pull steps found, exiting early." in result.output

    def test_clone_with_name_and_pull_step(
        self, flow, git_repository_mock, deployment_with_pull_step
    ):
        result = invoke_and_assert(
            command=(
                "project clone --deployment"
                f" '{flow.name}/{deployment_with_pull_step.name}'"
            ),
            expected_code=0,
            expected_output_contains="hello-projects",
        )
        assert result.exit_code == 0

    def test_clone_with_id_and_pull_steps(
        self, git_repository_mock, deployment_with_pull_steps
    ):
        result = invoke_and_assert(
            f"project clone --id {deployment_with_pull_steps.id}",
            expected_code=0,
            expected_output_contains="marvin",
        )
        assert result.exit_code == 0
