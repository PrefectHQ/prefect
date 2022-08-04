from uuid import UUID

from prefect import flow
from prefect.cli.deployment import create_deployment_from_deployment_yaml
from prefect.deployments import DeploymentYAML
from prefect.filesystems import LocalFileSystem
from prefect.infrastructure.process import Process
from prefect.utilities.callables import parameter_schema


async def test_create_deployment_from_deployment_yaml(orion_client):
    @flow
    def test_flow():
        pass

    storage = await LocalFileSystem.load("local-test")
    deployment_yaml = DeploymentYAML(
        name="Test",
        parameter_openapi_schema=parameter_schema(test_flow),
        flow_name="test_flow",
        description="v1",
        version="1",
        manifest_path="path/file.json",
        tags=[],
        storage=storage,
        infrastructure=Process(),
    )
    deployment_id = await create_deployment_from_deployment_yaml(deployment_yaml)
    assert isinstance(deployment_id, UUID)
