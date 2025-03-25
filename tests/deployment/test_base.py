import shutil
from pathlib import Path

import pytest
import yaml

import prefect
from prefect.deployments.base import (
    configure_project_by_recipe,
    initialize_project,
)
from prefect.utilities.filesystem import tmpchdir

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


@pytest.fixture(autouse=True)
def project_dir(tmp_path):
    with tmpchdir(tmp_path):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        (tmp_path / ".prefect").mkdir(exist_ok=True, mode=0o0700)
        yield tmp_path


class TestRecipes:
    async def test_configure_project_by_recipe_raises(self):
        with pytest.raises(ValueError, match="Unknown recipe"):
            configure_project_by_recipe("not-a-recipe")

    @pytest.mark.parametrize(
        "recipe",
        [
            d.absolute().name
            for d in Path(
                prefect.__development_base_path__
                / "src"
                / "prefect"
                / "deployments"
                / "recipes"
            ).iterdir()
            if d.is_dir()
        ],
    )
    async def test_configure_project_by_recipe_doesnt_raise(self, recipe):
        recipe_config = configure_project_by_recipe(recipe)
        for key in ["name", "prefect-version", "build", "push", "pull"]:
            assert key in recipe_config

    @pytest.mark.parametrize(
        "recipe",
        [
            d.absolute().name
            for d in Path(
                prefect.__development_base_path__
                / "src"
                / "prefect"
                / "deployments"
                / "recipes"
            ).iterdir()
            if d.is_dir() and "git" in d.absolute().name
        ],
    )
    async def test_configure_project_handles_templates_on_git_recipes(self, recipe):
        recipe_config = configure_project_by_recipe(
            recipe, repository="test-org/test-repo"
        )
        clone_step = recipe_config["pull"][0]["prefect.deployments.steps.git_clone"]
        assert clone_step["repository"] == "test-org/test-repo"
        assert clone_step["branch"] == "{{ branch }}"

    async def test_configure_project_replaces_templates_on_docker(self):
        recipe_config = configure_project_by_recipe("docker", name="test-dir")
        clone_step = recipe_config["pull"][0][
            "prefect.deployments.steps.set_working_directory"
        ]
        assert clone_step["directory"] == "/opt/prefect/test-dir"


class TestInitProject:
    async def test_initialize_project_works(self):
        files = initialize_project()
        assert len(files) >= 2

        for file in files:
            assert Path(file).exists()

        # test defaults
        with open("prefect.yaml", "r") as f:
            contents = yaml.safe_load(f)

        assert contents["name"] is not None
        assert contents["prefect-version"] == prefect.__version__

    async def test_initialize_project_with_name(self):
        files = initialize_project(name="my-test-its-a-test")
        assert len(files) >= 2

        with open("prefect.yaml", "r") as f:
            contents = yaml.safe_load(f)

        assert contents["name"] == "my-test-its-a-test"

    async def test_initialize_project_with_recipe(self):
        files = initialize_project(recipe="docker-git")
        assert len(files) >= 2

        with open("prefect.yaml", "r") as f:
            contents = yaml.safe_load(f)

        clone_step = contents["pull"][0]
        assert "prefect.deployments.steps.git_clone" in clone_step

        build_step = contents["build"][0]
        assert "prefect_docker.deployments.steps.build_docker_image" in build_step

    @pytest.mark.parametrize(
        "recipe",
        [
            d.absolute().name
            for d in Path(
                prefect.__development_base_path__
                / "src"
                / "prefect"
                / "deployments"
                / "recipes"
            ).iterdir()
            if d.is_dir() and "docker" in d.absolute().name
        ],
    )
    async def test_initialize_project_with_docker_recipe_default_image(self, recipe):
        files = initialize_project(recipe=recipe)
        assert len(files) >= 2

        with open("prefect.yaml", "r") as f:
            contents = yaml.safe_load(f)

        build_step = contents["build"][0]
        assert "prefect_docker.deployments.steps.build_docker_image" in build_step

        assert (
            contents["deployments"][0]["work_pool"]["job_variables"]["image"]
            == "{{ build_image.image }}"
        )
