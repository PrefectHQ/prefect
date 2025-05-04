import shutil
from pathlib import Path

import pytest
from anyio import Path as AnyioPath

import prefect
from prefect.cli._prompts import (
    find_flow_functions_in_file,
    search_for_flow_functions,
)
from prefect.settings import PREFECT_DEBUG_MODE, temporary_settings
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.filesystem import tmpchdir

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


@pytest.fixture(autouse=True)
def project_dir(tmp_path: Path):
    with tmpchdir(str(tmp_path)):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        (tmp_path / ".prefect").mkdir(exist_ok=True, mode=0o0700)
        yield tmp_path


class TestDiscoverFlows:
    async def test_find_all_flows_in_dir_tree(self, project_dir: Path):
        flows = await search_for_flow_functions(str(project_dir))
        assert len(flows) == 7, f"Expected 7 flows, found {len(flows)}"

        expected_flows = [
            {
                "flow_name": "foobar",
                "function_name": "foobar",
                "filepath": str(
                    project_dir / "nested-project" / "implicit_relative.py"
                ),
            },
            {
                "flow_name": "foobar",
                "function_name": "foobar",
                "filepath": str(
                    project_dir / "nested-project" / "explicit_relative.py"
                ),
            },
            {
                "flow_name": "An important name",
                "function_name": "my_flow",
                "filepath": str(project_dir / "flows" / "hello.py"),
            },
            {
                "flow_name": "Second important name",
                "function_name": "my_flow2",
                "filepath": str(project_dir / "flows" / "hello.py"),
            },
            {
                "flow_name": "test",
                "function_name": "prod_flow",
                "filepath": str(
                    project_dir / "import-project" / "my_module" / "flow.py"
                ),
            },
            {
                "flow_name": "test",
                "function_name": "test_flow",
                "filepath": str(
                    project_dir / "import-project" / "my_module" / "flow.py"
                ),
            },
            {
                "flow_name": "uses_block",
                "function_name": "uses_block",
                "filepath": str(project_dir / "flows" / "uses_block.py"),
            },
        ]

        assert sorted(
            expected_flows,
            key=lambda x: (x["flow_name"], x["function_name"], x["filepath"]),
        ) == sorted(
            flows, key=lambda x: (x["flow_name"], x["function_name"], x["filepath"])
        )

    async def test_find_all_flows_works_on_large_directory_structures(self):
        flows = await search_for_flow_functions(
            str(prefect.__development_base_path__ / "tests")
        )
        assert len(flows) > 500

    async def test_find_flow_functions_in_file_returns_empty_list_on_file_error(
        self, caplog: pytest.LogCaptureFixture
    ):
        with temporary_settings({PREFECT_DEBUG_MODE: True}):
            assert await find_flow_functions_in_file(AnyioPath("foo.py")) == []
            assert "Could not open foo.py" in caplog.text

    async def test_excludes_site_packages(self, project_dir: Path):
        """Test that search_for_flow_functions excludes site-packages directories."""
        site_packages = project_dir / "lib" / "python3.8" / "site-packages"
        site_packages.mkdir(parents=True)
        (site_packages / "package" / "flows").mkdir(parents=True)
        (site_packages / "package" / "flows" / "flow.py").write_text(
            "from prefect import flow\n@flow\ndef site_pkg_flow(): pass"
        )

        (project_dir / "flow.py").write_text(
            "from prefect import flow\n@flow\ndef regular_flow(): pass"
        )

        flows = await search_for_flow_functions(str(project_dir))

        assert not any("site-packages" in flow["filepath"] for flow in flows)

        assert any(
            flow["flow_name"] == "regular_flow" and flow["filepath"].endswith("flow.py")
            for flow in flows
        )

    async def test_prefect_can_be_imported_from_non_main_thread(self):
        """testing due to `asyncio.Semaphore` error when importing prefect from a worker thread
        in python <= 3.9
        """

        def import_prefect():
            import prefect  # noqa: F401

        await run_sync_in_worker_thread(import_prefect)
