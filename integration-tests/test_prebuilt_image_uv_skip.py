"""
Verify that `_uv_run_command()` correctly skips `uv run` in a pre-built
Docker image where dependencies were installed at build time.

Simulates the pre-built image pattern from OSS-7980:
  1. pyproject.toml declaring prefect as a dependency present in WORKDIR
  2. Dependencies pre-installed via `uv pip install --system -e .`
  3. uv available on PATH

The test exercises the actual production code path:
  - `_find_prematerialized_python()` detects the editable install
  - `_uv_run_command()` returns an explicit `python -m prefect.flow_engine`
    command instead of `uv run`
  - `uv run` would create a redundant `.venv` (proving skipping it matters)

Requires: Docker daemon available.
Does NOT require a running Prefect server.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "prebuilt_image_fixtures"
PREFECT_ROOT = Path(__file__).resolve().parent.parent


def _docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
            timeout=10,
        )
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def build_prebuilt_image(build_dir: Path) -> str:
    """Assemble the build context and build a pre-built-image Docker image.

    Builds a wheel from the current branch, copies it and the fixture files
    into *build_dir*, then runs `docker build`.  Returns the image tag.
    """
    tag = f"prefect-prebuilt-test-{uuid4().hex[:8]}"

    for name in ("Dockerfile", "pyproject.toml", "flows.py", "check_uv_skip.py"):
        shutil.copy(FIXTURES_DIR / name, build_dir / name)

    # Build a wheel from the current branch so the image has our code.
    wheel_dir = build_dir / "prefect_wheel"
    wheel_dir.mkdir()
    subprocess.check_call(
        ["uv", "build", "--wheel", "--out-dir", str(wheel_dir), str(PREFECT_ROOT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    subprocess.check_call(
        ["docker", "build", "-t", tag, "."],
        cwd=str(build_dir),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    return tag


@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
def test_prebuilt_image_skips_uv_run(tmp_path: Path):
    """Pre-built image: _uv_run_command returns explicit python, not uv run."""
    tag = build_prebuilt_image(tmp_path)

    try:
        result = subprocess.run(
            ["docker", "run", "--rm", tag, "python", "/tmp/check_uv_skip.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"Container script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        output = json.loads(result.stdout.strip().split("\n")[-1])

        # _find_prematerialized_python detected the editable install
        assert output["python_found"] is not None, (
            "Should detect pre-materialized python via editable install"
        )

        # _uv_run_command returns an explicit python command, not uv run
        assert output["skips_uv_run"] is True, (
            "_uv_run_command should return python -m prefect.flow_engine, not uv run"
        )
        assert output["command_parts"][1:] == [
            "-m",
            "prefect.flow_engine",
            "flows.py:hello",
        ]

        # uv run would create a redundant .venv — this is the waste we avoid
        assert output["venv_created_by_uv_run"] is True, (
            "uv run should have created a .venv, proving it would reinstall deps"
        )
    finally:
        subprocess.run(["docker", "rmi", tag], capture_output=True)
