"""
Tests for `prefect.deployments.Deployment`
"""

import pytest

from prefect import flow
from prefect.client import OrionClient
from prefect.deployments import Deployment
from prefect.flow_runners import SubprocessFlowRunner, UniversalFlowRunner
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.packaging import OrionPackager
from prefect.packaging.base import PackageManifest


@flow
def my_flow(x: int = 1):
    pass


async def test_deployment_defaults(orion_client: OrionClient):
    deploy = Deployment(flow=my_flow)

    # Default packager type
    assert deploy.packager == OrionPackager()

    deployment_id = await deploy.create()
    deployment = await orion_client.read_deployment(deployment_id)

    # The flow data should be a package manifest
    manifest = deployment.flow_data.decode()
    assert isinstance(manifest, PackageManifest)

    # Default values for other fields
    assert deployment.name == my_flow.name
    assert deployment.parameters == {}
    assert deployment.flow_runner == UniversalFlowRunner().to_settings()
    assert deployment.schedule is None
    assert deployment.tags == []

    # The flow was registered
    assert deployment.flow_id == await orion_client.create_flow(my_flow)


async def test_deployment_name(orion_client: OrionClient):
    deploy = Deployment(flow=my_flow, name="test")

    deployment_id = await deploy.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.name == "test"


async def test_deployment_tags(orion_client: OrionClient):
    deploy = Deployment(flow=my_flow, tags=["a", "b"])

    deployment_id = await deploy.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.tags == ["a", "b"]


async def test_deployment_parameters(orion_client: OrionClient):
    deploy = Deployment(flow=my_flow, parameters={"x": 2})

    deployment_id = await deploy.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.parameters == {"x": 2}


@pytest.mark.parametrize("schedule", [{"interval": 10}, IntervalSchedule(interval=10)])
async def test_deployment_schedule(orion_client: OrionClient, schedule):
    deploy = Deployment(flow=my_flow, schedule=schedule)

    deployment_id = await deploy.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.schedule == IntervalSchedule(interval=10)


@pytest.mark.parametrize(
    "flow_runner",
    [
        {"typename": "subprocess", "config": {"env": {"FOO": "BAR"}}},
        SubprocessFlowRunner(env={"FOO": "BAR"}),
    ],
)
async def test_deployment_flow_runner(orion_client: OrionClient, flow_runner):
    deploy = Deployment(flow=my_flow, flow_runner=flow_runner)

    deployment_id = await deploy.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert (
        deployment.flow_runner == SubprocessFlowRunner(env={"FOO": "BAR"}).to_settings()
    )


#     assert isinstance(manifest, OrionPackageManifest)
#     unpackaged_flow = await manifest.unpackage()
#     assert unpackaged_flow == my_flow
