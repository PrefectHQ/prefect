import json
import os
import shutil

import pytest

import prefect
from prefect.projects.base import find_prefect_directory, register_flow

TEST_PROJECTS_DIR = prefect.__root_path__ / "tests" / "test-projects"


@pytest.fixture(autouse=True)
def project_dir():
    os.chdir(TEST_PROJECTS_DIR)
    (TEST_PROJECTS_DIR / ".prefect").mkdir(exist_ok=True)
    yield
    shutil.rmtree((TEST_PROJECTS_DIR / ".prefect"), ignore_errors=True)


class TestFindProject:
    async def test_find_project_works_in_root(self, tmp_path):
        # make hidden .prefect/ directory in tmp_path
        (tmp_path / ".prefect").mkdir()
        assert find_prefect_directory(tmp_path) == tmp_path / ".prefect"

    async def test_find_project_works_in_subdir(self, tmp_path):
        # make hidden .prefect/ directory in tmp_path
        (tmp_path / ".prefect").mkdir()
        (tmp_path / "subdir" / "subsubdir").mkdir(parents=True)
        assert (
            find_prefect_directory(tmp_path / "subdir" / "subsubdir")
            == tmp_path / ".prefect"
        )


class TestRegisterFlow:
    async def test_register_flow_works_in_root(self):
        f = await register_flow(
            str(TEST_PROJECTS_DIR / "import-project" / "my_module" / "flow.py")
            + ":test_flow"
        )
        assert f.name == "test"

        with open(TEST_PROJECTS_DIR / ".prefect" / "flows.json", "r") as f:
            flows = json.load(f)

        assert flows["test"] == "import-project/my_module/flow.py:test_flow"

    async def test_register_flow_allows_identical_calls(self):
        f = await register_flow(
            str(TEST_PROJECTS_DIR / "import-project" / "my_module" / "flow.py")
            + ":test_flow"
        )
        assert f.name == "test"

        f = await register_flow(
            str(TEST_PROJECTS_DIR / "import-project" / "my_module" / "flow.py")
            + ":test_flow"
        )
        assert f.name == "test"

    async def test_register_flow_disallows_overwrites(self):
        f = await register_flow(
            str(TEST_PROJECTS_DIR / "import-project" / "my_module" / "flow.py")
            + ":test_flow"
        )
        assert f.name == "test"

        with pytest.raises(ValueError, match="Conflicting entry found"):
            await register_flow(
                str(TEST_PROJECTS_DIR / "import-project" / "my_module" / "flow.py")
                + ":prod_flow"
            )

        f = await register_flow(
            str(TEST_PROJECTS_DIR / "import-project" / "my_module" / "flow.py")
            + ":prod_flow",
            force=True,
        )
        assert f.name == "test"
