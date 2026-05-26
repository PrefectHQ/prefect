"""
Verify that `_uv_run_command` returns None for pre-built Docker images where
dependencies are already installed at build time.

Simulates the pre-built image pattern from OSS-7980:
  1. pyproject.toml declaring prefect as a dependency present in WORKDIR
  2. Dependencies pre-installed via `uv pip install --system -e .`
  3. uv available on PATH

Expected: `_uv_run_command` returns None so the runner falls back to
`python -m prefect.flow_engine` instead of re-downloading everything.

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

REPO_ROOT = Path(__file__).resolve().parent.parent
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

    Copies the static fixture files and the local prefect source into
    *build_dir*, then runs `docker build`.  Returns the image tag.
    """
    tag = f"prefect-prebuilt-test-{uuid4().hex[:8]}"

    for name in ("Dockerfile", "pyproject.toml", "flows.py", "check_uv_skip.py"):
        shutil.copy(FIXTURES_DIR / name, build_dir / name)

    # Copy the workspace starter under test so the Dockerfile can overlay it.
    shutil.copy(
        REPO_ROOT / "src" / "prefect" / "runner" / "_workspace_starter.py",
        build_dir / "_workspace_starter.py",
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
    """When deps are pre-installed in a Docker image, _uv_run_command returns None."""
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

        assert output["project_is_installed"] is True, (
            "Project should be detected as installed in pre-built image"
        )
        assert output["uv_run_command"] is None, (
            f"Expected uv_run_command=None for pre-built image, "
            f"got: {output['uv_run_command']}"
        )
    finally:
        subprocess.run(["docker", "rmi", tag], capture_output=True)
