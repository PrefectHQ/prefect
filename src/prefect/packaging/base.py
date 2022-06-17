import abc

from pydantic import BaseModel

from prefect.deployments.base import DeploymentSpecification
from prefect.orion.schemas.actions import DeploymentCreate


class Packager(BaseModel, abc.ABC):
    async def validate(self, deployment: DeploymentSpecification) -> None:
        """
        Check compatbility with a deployment.
        """

    async def package(self, deployment: DeploymentSpecification) -> DeploymentCreate:
        """
        Package the flow referenced by the deployment.

        A schema for creating an API deployment will be returned with populated
        references to the packaged flow.
        """
