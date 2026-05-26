"""
Verify that _uv_run_command returns None for pre-built Docker images where
dependencies are already installed at build time.

Simulates the pre-built image pattern from OSS-7980:
  1. pyproject.toml declaring prefect as a dependency present in WORKDIR
  2. Dependencies pre-installed via `uv pip install --system -e .`
  3. uv available on PATH

Expected: _uv_run_command returns None so the runner falls back to
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
from textwrap import dedent
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SAMPLE_PYPROJECT = dedent("""\
    [project]
    name = "my-prebuilt-flow"
    version = "0.1.0"
    requires-python = ">=3.10"
    dependencies = ["prefect"]

    [build-system]
    requires = ["setuptools"]
    build-backend = "setuptools.build_meta"
""")

SAMPLE_FLOW = dedent("""\
    from prefect import flow

    @flow
    def hello():
        return "hello"
""")

CHECK_SCRIPT = dedent("""\
    import json
    import os
    from pathlib import Path

    from prefect.runner._workspace_resolver import PreparedWorkspace
    from prefect.runner._workspace_starter import _project_is_installed, _uv_run_command

    workdir = Path("/opt/prefect/flow")
    pyproject = workdir / "pyproject.toml"

    installed = _project_is_installed(pyproject)

    workspace = PreparedWorkspace(
        workspace_root=workdir,
        working_directory=workdir,
        project_root=workdir,
        runtime_entrypoint="flows.py:hello",
        environment=dict(os.environ),
        sys_path=[],
    )

    command = _uv_run_command(workspace)

    print(json.dumps({"project_is_installed": installed, "uv_run_command": command}))
""")

DOCKERFILE = dedent("""\
    FROM prefecthq/prefect:3-latest
    WORKDIR /opt/prefect/flow

    # Simulate the pre-built image pattern: install the project at build time
    COPY pyproject.toml flows.py ./
    RUN uv pip install --system -e .

    # Patch the runner with our fix so we can test it
    COPY _workspace_starter.py /tmp/_workspace_starter.py
    RUN SITE=$(python -c "import prefect.runner; from pathlib import Path; print(Path(prefect.runner.__file__).parent)") && \\
        cp /tmp/_workspace_starter.py "$SITE/_workspace_starter.py"

    COPY check_uv_skip.py /tmp/check_uv_skip.py
""")


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


@pytest.fixture
def prebuilt_image(tmp_path: Path):
    """Build a Docker image that simulates the pre-built deployment pattern."""
    tag = f"prefect-prebuilt-test-{uuid4().hex[:8]}"

    build_dir = tmp_path / "build"
    build_dir.mkdir()

    (build_dir / "pyproject.toml").write_text(SAMPLE_PYPROJECT)
    (build_dir / "flows.py").write_text(SAMPLE_FLOW)
    (build_dir / "check_uv_skip.py").write_text(CHECK_SCRIPT)
    (build_dir / "Dockerfile").write_text(DOCKERFILE)

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

    yield tag

    subprocess.run(["docker", "rmi", tag], capture_output=True)


@pytest.mark.skipif(not _docker_available(), reason="Docker daemon not available")
def test_prebuilt_image_skips_uv_run(prebuilt_image: str):
    """When deps are pre-installed in a Docker image, _uv_run_command returns None."""
    result = subprocess.run(
        ["docker", "run", "--rm", prebuilt_image, "python", "/tmp/check_uv_skip.py"],
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
