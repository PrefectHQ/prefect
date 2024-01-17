import os
import subprocess
import sys
from pathlib import Path

import anyio
from packaging.version import Version

import prefect
from prefect.deployments import Deployment
from prefect.filesystems import LocalFileSystem

# The version oldest version this test runs with
SUPPORTED_VERSION = "2.6.0"


if Version(prefect.__version__) < Version(SUPPORTED_VERSION):
    sys.exit(0)


@prefect.flow
def hello(name: str = "world"):
    prefect.get_run_logger().info(f"Hello {name}!")
    return foo() + bar()


@prefect.flow
def foo():
    return 1


@prefect.flow
async def bar():
    return 2


async def create_flow_run(deployment_id):
    async with prefect.get_client() as client:
        return await client.create_flow_run_from_deployment(
            deployment_id, parameters={"name": "integration tests"}
        )


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def main():
    # We must create an ignore file
    file = Path(".prefectignore")
    if not file.exists():
        file.touch()

    # Create deployment
    deployment = Deployment.build_from_flow(
        flow=hello,
        name="test-deployment",
        storage=LocalFileSystem(basepath="/tmp/integration-flows/storage"),
        path=None,
    )
    deployment_id = deployment.apply()

    # Create a flow run
    flow_run = anyio.run(create_flow_run, deployment_id)

    os.makedirs("/tmp/integration-flows/execution", exist_ok=True)

    env = os.environ.copy()
    env["PREFECT__FLOW_RUN_ID"] = str(flow_run.id)
    subprocess.check_call(
        [sys.executable, "-m", "prefect.engine"],
        env=env,
        timeout=30,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd="/tmp/integration-flows/execution",
    )

    flow_run = anyio.run(read_flow_run, flow_run.id)
    assert flow_run.state.is_completed(), flow_run.state


if __name__ == "__main__":
    main()
