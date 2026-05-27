"""
End-to-end test: pre-built Docker image deployments skip `uv run`.

Exercises the full deployment execution path reported in OSS-7980:

    prefect flow-run execute <id>
      -> WorkspaceResolvingEngineCommandStarter
        -> workspace resolver (pull step: set_working_directory)
        -> command selection (_find_prematerialized_python)
        -> child `python -m prefect.flow_engine` process
        -> actual flow execution

The Docker image is built by CI (see `.github/workflows/integration-tests.yaml`)
and passed via the `PREBUILT_IMAGE_TAG` env var.  When running locally without
that var, the fixture builds the image on the fly.

The flow itself asserts observable behaviour:
  - cwd == /opt/prefect/flow
  - no .venv was created (proving `uv run` did not materialize a project env)
  - sys.executable is not inside a .venv

Requires: Docker daemon available, Prefect server at PREFECT_API_URL.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import anyio
import pytest

import prefect

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


def _build_image_locally(build_dir: Path) -> str:
    """Build the prebuilt-image fixture from scratch (local dev fallback)."""
    tag = f"prefect-prebuilt-test-{uuid4().hex[:8]}"

    for name in ("Dockerfile", "pyproject.toml", "flows.py"):
        shutil.copy(FIXTURES_DIR / name, build_dir / name)

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


@pytest.fixture(scope="module")
def prebuilt_image(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Return the prebuilt Docker image tag.

    Uses `PREBUILT_IMAGE_TAG` from CI when available; otherwise builds
    the image locally.  Cleans up locally-built images after the module.
    """
    if not _docker_available():
        pytest.skip("Docker daemon not available")

    ci_tag = os.environ.get("PREBUILT_IMAGE_TAG")
    if ci_tag:
        yield ci_tag
        return

    build_dir = tmp_path_factory.mktemp("prebuilt_image")
    tag = _build_image_locally(build_dir)

    yield tag

    subprocess.run(["docker", "rmi", tag], capture_output=True)


async def _create_flow_run() -> str:
    """Create a deployment with set_working_directory pull step and a flow run."""
    async with prefect.get_client() as client:
        flow_id = await client.create_flow_from_name(
            f"prebuilt-image-test-{uuid4().hex[:8]}"
        )
        deployment_id = await client.create_deployment(
            flow_id=flow_id,
            name=f"prebuilt-deploy-{uuid4().hex[:8]}",
            entrypoint="flows.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": "/opt/prefect/flow",
                    }
                }
            ],
        )
        flow_run = await client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )
        return str(flow_run.id)


async def _read_flow_run(flow_run_id: str) -> prefect.client.schemas.objects.FlowRun:
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def test_prebuilt_image_flow_run_completes(prebuilt_image: str):
    """Flow run executes to completion inside the prebuilt image without uv run."""
    api_url = os.environ.get("PREFECT_API_URL")
    if not api_url:
        pytest.skip("PREFECT_API_URL not set")

    flow_run_id = anyio.run(_create_flow_run)

    # Normalize localhost for Docker on Linux (CI uses --network host)
    container_api_url = api_url

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "-e",
            f"PREFECT_API_URL={container_api_url}",
            prebuilt_image,
            "prefect",
            "flow-run",
            "execute",
            flow_run_id,
        ],
        capture_output=True,
        text=True,
    )

    flow_run = anyio.run(_read_flow_run, flow_run_id)

    assert result.returncode == 0, (
        f"Flow run execute command failed with exit code {result.returncode}.\n"
        f"Container stdout:\n{result.stdout}\n"
        f"Container stderr:\n{result.stderr}"
    )
    assert flow_run.state is not None and flow_run.state.is_completed(), (
        f"Flow run did not complete.\n"
        f"State: {flow_run.state}\n"
        f"Container stdout:\n{result.stdout}\n"
        f"Container stderr:\n{result.stderr}"
    )
