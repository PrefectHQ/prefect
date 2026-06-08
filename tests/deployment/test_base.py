import shutil
from pathlib import Path

import pytest
import yaml

import prefect
from prefect.deployments.base import (
    _deployment_already_saved_to_prefect_file,
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


class TestDeploymentAlreadySavedToPrefectFile:
    """
    Unit coverage for the matching check that gates the interactive save prompt
    in `prefect deploy`.  Restores coverage removed in #17519 and underpins the
    fix for #17409 (don't re-prompt already-declared deployments) and the Slack
    report (do prompt for new deployments in an existing file).
    """

    def _write(self, deployments) -> Path:
        prefect_file = Path("prefect.yaml")
        with prefect_file.open(mode="w") as f:
            yaml.safe_dump({"deployments": deployments}, f)
        return prefect_file

    def test_returns_false_when_file_missing(self):
        assert not _deployment_already_saved_to_prefect_file(
            {"name": "x", "entrypoint": "flows/hello.py:my_flow"},
            prefect_file=Path("does-not-exist.yaml"),
        )

    def test_returns_true_on_name_and_entrypoint_match(self):
        prefect_file = self._write(
            [{"name": "x", "entrypoint": "flows/hello.py:my_flow"}]
        )
        assert _deployment_already_saved_to_prefect_file(
            {"name": "x", "entrypoint": "flows/hello.py:my_flow"},
            prefect_file=prefect_file,
        )

    def test_returns_false_when_name_matches_but_entrypoint_differs(self):
        prefect_file = self._write(
            [{"name": "x", "entrypoint": "flows/hello.py:my_flow"}]
        )
        assert not _deployment_already_saved_to_prefect_file(
            {"name": "x", "entrypoint": "flows/other.py:my_flow"},
            prefect_file=prefect_file,
        )

    def test_returns_false_for_new_deployment_in_scaffolded_file(self):
        # an `init`-scaffolded file has a single null-field placeholder entry;
        # a real deployment must not match it (the Slack-reported case)
        initialize_project()
        assert not _deployment_already_saved_to_prefect_file(
            {"name": "default", "entrypoint": "flows/hello.py:my_flow"},
        )

    def test_returns_false_when_no_deployments_declared(self):
        self._write(None)
        assert not _deployment_already_saved_to_prefect_file(
            {"name": "x", "entrypoint": "flows/hello.py:my_flow"},
        )
