"""
Tests for `prefect.deployments.Deployment`
"""

import pydantic
import pytest

from prefect import flow
from prefect.client import OrionClient
from prefect.context import PrefectObjectRegistry
from prefect.deployments import Deployment, FlowScript
from prefect.flow_runners import SubprocessFlowRunner, UniversalFlowRunner
from prefect.flows import Flow
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.packaging import FilePackager, OrionPackager
from prefect.packaging.base import PackageManifest


@flow
def my_flow(x: int = 1):
    pass


def test_deployment_added_to_registry():
    dpl1 = Deployment(flow=my_flow)
    assert PrefectObjectRegistry.get().deployments == [dpl1]
    dpl2 = Deployment(flow=my_flow)
    assert PrefectObjectRegistry.get().deployments == [dpl1, dpl2]


def test_deployment_not_added_to_registry_on_failure():
    with pytest.raises(pydantic.ValidationError):
        Deployment(flow="foobar")

    assert PrefectObjectRegistry.get().deployments == []


async def test_deployment_defaults(orion_client: OrionClient):
    dpl = Deployment(flow=my_flow)

    # Default packager type
    assert dpl.packager == OrionPackager()

    deployment_id = await dpl.create()
    deployment = await orion_client.read_deployment(deployment_id)

    # Default values for fields
    assert deployment.name == my_flow.name
    assert deployment.parameters == {}
    assert deployment.flow_runner == UniversalFlowRunner().to_settings()
    assert deployment.schedule is None
    assert deployment.tags == []

    # The flow was registered
    assert deployment.flow_id == await orion_client.create_flow(my_flow)

    # The flow data should be a package manifest
    manifest = deployment.flow_data.decode()
    assert isinstance(manifest, PackageManifest)


async def test_deployment_name(orion_client: OrionClient):
    dpl = Deployment(flow=my_flow, name="test")

    deployment_id = await dpl.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.name == "test"


async def test_deployment_tags(orion_client: OrionClient):
    dpl = Deployment(flow=my_flow, tags=["a", "b"])

    deployment_id = await dpl.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.tags == ["a", "b"]


async def test_deployment_parameters(orion_client: OrionClient):
    dpl = Deployment(flow=my_flow, parameters={"x": 2})

    deployment_id = await dpl.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.parameters == {"x": 2}


@pytest.mark.parametrize("schedule", [{"interval": 10}, IntervalSchedule(interval=10)])
async def test_deployment_schedule(orion_client: OrionClient, schedule):
    dpl = Deployment(flow=my_flow, schedule=schedule)

    deployment_id = await dpl.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.schedule == IntervalSchedule(interval=10)


@pytest.mark.parametrize(
    "flow_runner",
    [
        {"type": "subprocess", "config": {"env": {"FOO": "BAR"}}},
        SubprocessFlowRunner(env={"FOO": "BAR"}),
    ],
)
async def test_deployment_flow_runner(orion_client: OrionClient, flow_runner):
    dpl = Deployment(flow=my_flow, flow_runner=flow_runner)

    deployment_id = await dpl.create()

    deployment = await orion_client.read_deployment(deployment_id)
    assert (
        deployment.flow_runner == SubprocessFlowRunner(env={"FOO": "BAR"}).to_settings()
    )


@pytest.mark.parametrize(
    "flow_script",
    [{"path": __file__, "name": "my-flow"}, FlowScript(path=__file__, name="my-flow")],
)
async def test_deployment_flow_script_source(flow_script, orion_client: OrionClient):
    dpl = Deployment(flow=flow_script)

    deployment_id = await dpl.create()
    deployment = await orion_client.read_deployment(deployment_id)

    # The flow data should be a package manifest
    manifest = deployment.flow_data.decode()
    assert isinstance(manifest, PackageManifest)

    flow = await manifest.unpackage()
    assert isinstance(flow, Flow)
    assert flow.name == "my-flow"


async def test_deployment_manifest_source(orion_client: OrionClient):
    manifest = await OrionPackager().package(my_flow)
    dpl = Deployment(flow=manifest)

    deployment_id = await dpl.create()
    deployment = await orion_client.read_deployment(deployment_id)

    # The flow data should be a package manifest
    server_manifest = deployment.flow_data.decode()
    assert server_manifest == manifest


@pytest.mark.parametrize(
    "packager",
    [
        {"type": "file"},
        FilePackager(),
    ],
)
async def test_deployment_packager_can_be_dict_or_instance(
    orion_client: OrionClient, packager
):
    dpl = Deployment(flow=my_flow, packager=packager)
    assert dpl.packager == FilePackager()


@pytest.mark.parametrize(
    "packager",
    [
        OrionPackager(),
        FilePackager(),
    ],
)
async def test_deployment_by_packager_type(orion_client: OrionClient, packager):
    dpl = Deployment(flow=my_flow, packager=packager)

    deployment_id = await dpl.create()

    deployment = await orion_client.read_deployment(deployment_id)

    # The flow data should be a package manifest
    manifest = deployment.flow_data.decode()
    assert isinstance(manifest, PackageManifest)

    flow = await manifest.unpackage()
    assert isinstance(flow, Flow)
    assert flow.name == "my-flow"
