import asyncio
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import uv

from prefect import flow, get_client
from prefect.deployments import run_deployment
from prefect.docker.docker_image import DockerImage


async def read_flow_run(flow_run_id: str):
    """Read a flow run's state using the Prefect client."""
    async with get_client() as client:
        return await client.read_flow_run(flow_run_id)


@flow
def flow_that_needs_pandas() -> str:
    """A flow that needs pandas."""
    import pandas

    df = pandas.DataFrame({"a": [1, 2, 3]})

    assert isinstance(df, pandas.DataFrame)

    return "we're done"


def test_docker_deploy():
    """
    Deploy and run a flow in a Docker container with runtime package installation using uv.
    Demonstrates using EXTRA_PIP_PACKAGES to install dependencies at runtime.
    """
    try:
        subprocess.check_call(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "work-pool",
                "create",
                "test-docker-pool",
                "-t",
                "docker",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        dockerfile = Path("docker-deploy.Dockerfile")

        dockerfile.write_text(
            dedent(
                """
                FROM prefecthq/prefect:3-latest
                COPY integration-tests/test_docker_deploy.py /opt/prefect/integration-tests/test_docker_deploy.py
                """
            )
        )

        flow_that_needs_pandas.deploy(
            name="docker-demo-deployment",
            work_pool_name="test-docker-pool",
            job_variables={
                "env": {"EXTRA_PIP_PACKAGES": "pandas"},
                "image": "prefect-integration-test-docker-deploy",
            },
            image=DockerImage(
                name="prefect-integration-test-docker-deploy",
                dockerfile=str(dockerfile),
            ),
            build=True,
            push=False,
        )

        dockerfile.unlink()

        flow_run = run_deployment(
            "flow-that-needs-pandas/docker-demo-deployment",
            timeout=0,
        )

        # Execute the flow run
        subprocess.check_call(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "--with",
                "prefect-docker",
                "prefect",
                "worker",
                "start",
                "--pool",
                "test-docker-pool",
                "--run-once",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        # Check the flow run state
        flow_run = asyncio.run(read_flow_run(flow_run.id))
        assert flow_run.state.is_completed(), flow_run.state

    finally:
        # Cleanup
        subprocess.check_call(
            [
                uv.find_uv_bin(),
                "run",
                "--isolated",
                "prefect",
                "--no-prompt",
                "work-pool",
                "delete",
                "test-docker-pool",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
