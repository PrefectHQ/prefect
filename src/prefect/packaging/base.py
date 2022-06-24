import abc
from typing import Generic, TypeVar

from pydantic import BaseModel

from prefect.flows import Flow
from prefect.utilities.pydantic import add_type_dispatch

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

    # The packager implementation for this manifest
    __packager__: "Packager"


@add_type_dispatch
class Packager(BaseModel, abc.ABC):
    """
    Creates a package for a flow.

    A package contains the flow and is typically stored outside of Prefect. To faciliate
    interaction with the package, a manifest is returned that describes how to access
    and use the package.
    """

    type: str

    @abc.abstractmethod
    async def package(self, flow: Flow) -> "PackageManifest":
        """
        Package a flow and return a manifest describing the created package.
        """

    @abc.abstractstaticmethod
    def unpackage(manifest: "PackageManifest") -> Flow:
        """
        Retrieve a flow from a package.
        """
