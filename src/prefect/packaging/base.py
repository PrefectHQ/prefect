import abc
from typing import Generic, TypeVar

from pydantic import BaseModel

from prefect.flows import Flow
from prefect.utilities.callables import ParameterSchema, parameter_schema
from prefect.utilities.dispatch import lookup_type
from prefect.utilities.pydantic import PartialModel, add_type_dispatch

D = TypeVar("D")


@add_type_dispatch
class Serializer(BaseModel, Generic[D], abc.ABC):
    """
    A serializer that can encode objects of type 'D' into bytes.
    """

    type: str

    def dumps(self, obj: D) -> bytes:
        """Encode the object into a blob of bytes."""

    def loads(self, blob: bytes) -> D:
        """Decode the blob of bytes into an object."""


@add_type_dispatch
class PackageManifest(BaseModel, abc.ABC):
    """
    Describes a package.
    """

    type: str
    flow_name: str
    flow_parameter_schema: ParameterSchema

    @abc.abstractmethod
    async def unpackage(self) -> Flow:
        """
        Retrieve a flow from the package.
        """


@add_type_dispatch
class Packager(BaseModel, abc.ABC):
    """
    Creates a package for a flow.

    A package contains the flow and is typically stored outside of Prefect. To
    facilitate interaction with the package, a manifest is returned that describes how
    to access and use the package.
    """

    type: str

    def base_manifest(self, flow: Flow) -> PartialModel[PackageManifest]:
        manifest_cls = lookup_type(PackageManifest, self.type)
        return PartialModel(
            manifest_cls,
            type=self.type,
            flow_name=flow.name,
            flow_parameter_schema=parameter_schema(flow.fn),
        )

    @abc.abstractmethod
    async def package(self, flow: Flow) -> "PackageManifest":
        """
        Package a flow and return a manifest describing the created package.
        """
