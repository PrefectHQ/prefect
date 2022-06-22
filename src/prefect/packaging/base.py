import abc
from typing import TYPE_CHECKING, Generic, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from prefect.deployments import FlowSource

D = TypeVar("D")


class Serializer(BaseModel, Generic[D], abc.ABC):
    """
    A serializer that can encode objects of type 'D' into bytes.
    """

    def dumps(self, obj: D) -> bytes:
        """Encode the object into a blob of bytes."""

    def loads(self, blob: bytes) -> D:
        """Decode the blob of bytes into an object."""


class PackageManifest(BaseModel, abc.ABC):
    """
    Describes a package.
    """


class Packager(BaseModel, abc.ABC):
    """
    Creates a package for a flow.
    """

    @abc.abstractmethod
    async def package(self, flow: "FlowSource") -> PackageManifest:
        """
        Package a flow and returns a manifest describing how the package can be used
        in a deployment.
        """
