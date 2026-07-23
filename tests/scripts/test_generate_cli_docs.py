"""Smoke tests for scripts/generate_cli_docs.py"""

import runpy
from pathlib import Path
from typing import Callable

import pytest


@pytest.fixture(scope="module")
def script_path(tests_dir: Path) -> Path:
    return tests_dir.parent / "scripts" / "generate_cli_docs.py"


@pytest.fixture(scope="module")
def generate_cli_docs(script_path: Path) -> Callable[[str], None]:
    """Load the generate_cli_docs function from the script."""
    globals_ = runpy.run_path(str(script_path))
    return globals_["generate_cli_docs"]


def test_generate_cli_docs_produces_experimental_without_stale_safe_mode(
    generate_cli_docs: Callable[[str], None],
    tmp_path: Path,
):
    output_dir = tmp_path / "cli"
    generate_cli_docs(str(output_dir))

    experimental_path = output_dir / "experimental.mdx"
    assert experimental_path.exists(), "experimental.mdx should be generated"

    content = experimental_path.read_text()
    assert "prefect experimental" in content
    assert "prefect experimental plugins diagnose" in content
    assert "PREFECT_EXPERIMENTS_PLUGINS_SAFE_MODE" not in content

    api_path = output_dir / "api.mdx"
    assert api_path.exists(), "api.mdx should be generated"
    api_content = api_path.read_text()
    assert "HTTP method" in api_content, "api METHOD description should be present"
    assert "API path" in api_content, "api PATH description should be present"
    assert "$ prefect api GET /flows" in api_content, "api examples should be present"

    plugins_path = output_dir / "plugins.mdx"
    assert plugins_path.exists(), "plugins.mdx should be generated"
    plugins_content = plugins_path.read_text()
    assert "prefect plugins" in plugins_content, "plugins command should be documented"

    automation_path = output_dir / "automation.mdx"
    assert automation_path.exists(), "automation.mdx should be generated"
    automation_content = automation_path.read_text()
    assert "An automation's name." in automation_content, (
        "automation NAME argument help should be present"
    )
    assert "$ prefect automation create --from-file" in automation_content, (
        "automation create examples should be present"
    )
    assert "$ prefect automation update --id" in automation_content, (
        "automation update examples should be present"
    )

    flow_run_path = output_dir / "flow-run.mdx"
    assert flow_run_path.exists(), "flow-run.mdx should be generated"
    flow_run_content = flow_run_path.read_text()
    assert "$ prefect flow-run retry" in flow_run_content, (
        "flow-run retry examples should be present"
    )

    sdk_path = output_dir / "sdk.mdx"
    assert sdk_path.exists(), "sdk.mdx should be generated"
    sdk_content = sdk_path.read_text()
    assert "$ prefect sdk generate --output ./my_sdk.py" in sdk_content, (
        "sdk generate examples should be present"
    )

    work_pool_path = output_dir / "work-pool.mdx"
    assert work_pool_path.exists(), "work-pool.mdx should be generated"
    work_pool_content = work_pool_path.read_text()
    assert "$ prefect work-pool ls" in work_pool_content, (
        "work-pool examples should be present"
    )

    shell_path = output_dir / "shell.mdx"
    assert shell_path.exists(), "shell.mdx should be generated"
    shell_content = shell_path.read_text()
    serve_section = shell_content.split("## `prefect shell serve`", 1)[-1]
    assert "--log-output" not in serve_section, (
        "hidden shell serve --log-output option should not be documented"
    )
