"""
Verify that the `_project_is_installed` detection mechanism works correctly
in a pre-built Docker image where dependencies were installed at build time.

Simulates the pre-built image pattern from OSS-7980:
  1. pyproject.toml declaring prefect as a dependency present in WORKDIR
  2. Dependencies pre-installed via `uv pip install --system -e .`
  3. uv available on PATH

The test proves three things:
  - The project is discoverable via `importlib.metadata` (our detection signal)
  - Prefect is already importable at the expected version without `uv run`
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

    Copies the static fixture files into *build_dir*, then runs
    `docker build`.  Returns the image tag.
    """
    tag = f"prefect-prebuilt-test-{uuid4().hex[:8]}"

    for name in ("Dockerfile", "pyproject.toml", "flows.py", "check_uv_skip.py"):
        shutil.copy(FIXTURES_DIR / name, build_dir / name)

    subprocess.check_call(
        ["docker", "build", "-t", tag, "."],
        cwd=str(build_dir),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    return tag


@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
def test_prebuilt_image_skips_uv_run(tmp_path: Path):
    """Pre-built image: project is detectable, prefect is present, uv run is redundant."""
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

        # The project declared in pyproject.toml is discoverable — this is
        # the signal _project_is_installed uses to skip uv run.
        assert output["project_name"] == "my-prebuilt-flow"
        assert output["project_installed"] is True, (
            "Project should be detected as installed in pre-built image"
        )

        # Prefect is already available at a known version without uv run.
        assert output["prefect_version"], "Prefect should be importable"

        # uv run would create a redundant .venv — this is the waste we avoid.
        assert output["venv_created_by_uv_run"] is True, (
            "uv run should have created a .venv, proving it would reinstall deps"
        )
    finally:
        subprocess.run(["docker", "rmi", tag], capture_output=True)
