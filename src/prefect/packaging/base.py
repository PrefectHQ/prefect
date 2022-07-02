import abc
from typing import TYPE_CHECKING

from pydantic import BaseModel

from prefect.orion.schemas.actions import DeploymentCreate

if TYPE_CHECKING:
    from prefect.deployments import DeploymentSpec


class Packager(BaseModel, abc.ABC):
    @abc.abstractmethod
    async def check_compat(self, deployment: "DeploymentSpec") -> None:
        """
        Check compatbility with a deployment.
        """

    @abc.abstractmethod
    async def package(self, deployment: "DeploymentSpec") -> DeploymentCreate:
        """
        Package the flow referenced by the deployment.

        A schema for creating an API deployment will be returned with populated
        references to the packaged flow.
        """
