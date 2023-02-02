import os
import pathlib
import subprocess

import anyio
from packaging.version import Version

import prefect
from prefect.deployments import Deployment
from prefect.utilities.callables import parameter_schema


@prefect.flow
def hello(name: str = "world"):
    prefect.get_run_logger().info(f"Hello {name}!")


async def apply_deployment_20(deployment):
    async with prefect.get_client() as client:
        flow_id = await client.create_flow_from_name(deployment.flow_name)
        return await client.create_deployment(
            flow_id=flow_id,
            name=deployment.name,
            path=deployment.path,
            entrypoint=deployment.entrypoint,
        )


async def create_flow_run(deployment_id):
    async with prefect.get_client() as client:
        return await client.create_flow_run_from_deployment(
            deployment_id, parameters={"name": "integration tests"}
        )


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


def main():
    # Create deployment
    if Version(prefect.__version__) < Version("2.1.0"):
        deployment = Deployment(
            name="test-deployment",
            flow_name=hello.name,
            parameter_openapi_schema=parameter_schema(hello),
            path=str(pathlib.Path(__file__).parent),
            entrypoint=f"{__file__}:hello",
        )
        deployment_id = anyio.run(apply_deployment_20, deployment)
    else:
        deployment = Deployment.build_from_flow(flow=hello, name="test-deployment")
        deployment_id = deployment.apply()

    # Create a flow run
    flow_run = anyio.run(create_flow_run, deployment_id)

    TEST_SERVER_VERSION = os.environ.get("TEST_SERVER_VERSION")

    if Version(prefect.__version__) < Version("2.1"):
        # work queue is positional instead of a flag and requires creation
        subprocess.run(["prefect", "work-queue", "create", "test"])
        try:
            subprocess.run(["prefect", "agent", "start", "test"], timeout=30)
        except subprocess.TimeoutExpired:
            pass
    elif (
        Version(prefect.__version__) > Version("2.6")
        and TEST_SERVER_VERSION
        and Version(TEST_SERVER_VERSION) < Version("2.7")
        and Version(TEST_SERVER_VERSION) > Version("2.5")
    ):
        print(
            "A CANCELLING state type was added in 2.7 so when the agent (client) "
            "is running 2.7+ and the server is running 2.6 checks for cancelled flows "
            "will fail. This is a known incompatibility."
        )
        return
    elif Version(prefect.__version__) < Version("2.6"):
        # --run-once is not available so just run for a bit
        try:
            subprocess.run(
                ["prefect", "agent", "start", "--work-queue", "default"], timeout=30
            )
        except subprocess.TimeoutExpired:
            pass
    else:
        subprocess.check_call(
            ["prefect", "agent", "start", "--run-once", "--work-queue", "default"],
        )

    flow_run = anyio.run(read_flow_run, flow_run.id)
    assert flow_run.state.is_completed()


if __name__ == "__main__":
    main()
