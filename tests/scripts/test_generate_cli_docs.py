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
