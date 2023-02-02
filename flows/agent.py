import subprocess

import anyio
from packaging.version import Version

import prefect
from prefect.deployments import Deployment
from prefect.utilities.callables import parameter_schema


@prefect.flow
def hello(name: str = "world"):
    prefect.get_run_logger().info(f"Hello {name}!")


async def apply_deployment(deployment):
    async with prefect.get_client() as client:
        flow_id = await client.create_flow_from_name(deployment.flow_name)
        return await client.create_deployment(flow_id=flow_id, name=deployment.name)


async def create_flow_run(deployment_id):
    async with prefect.get_client() as client:
        return await client.create_flow_run_from_deployment(
            deployment_id, parameters={"name": "integration tests"}
        )


async def read_flow_run(flow_run_id):
    async with prefect.get_client() as client:
        return await client.read_flow_run(flow_run_id)


if __name__ == "__main__":
    # Create deployment
    if Version(prefect.__version__) < Version("2.1.0"):
        deployment = Deployment(
            name="test-deployment",
            flow_name=hello.name,
            parameter_openapi_schema=parameter_schema(hello),
        )
        deployment_id = anyio.run(apply_deployment, deployment)
    else:
        deployment = Deployment.build_from_flow(flow=hello, name="test-deployment")
        deployment_id = deployment.apply()

    # Update deployment
    deployment.tags = ["test"]
    if Version(prefect.__version__) >= Version("2.1.0"):
        deployment_id = deployment.apply()

    flow_run = anyio.run(create_flow_run, deployment_id)

    subprocess.check_call(
        ["prefect", "agent", "start", "--run-once", "--work-queue", "default"],
    )

    flow_run = anyio.run(read_flow_run, flow_run.id)
    assert flow_run.state.is_completed()
