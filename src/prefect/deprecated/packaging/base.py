"""
DEPRECATION WARNING:
This module is deprecated as of March 2024 and will not be available after September 2024.
"""

import abc
from typing import Generic, Type, TypeVar

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel
else:
    from pydantic import BaseModel

from prefect.flows import Flow
from prefect.utilities.callables import ParameterSchema, parameter_schema
from prefect.utilities.dispatch import lookup_type
from prefect.utilities.pydantic import add_type_dispatch

D = TypeVar("D")


@deprecated_class(start_date="Mar 2024")
@add_type_dispatch
class Serializer(BaseModel, Generic[D], abc.ABC):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    A serializer that can encode objects of type 'D' into bytes.
    """

    type: str

    def dumps(self, obj: D) -> bytes:
        """Encode the object into a blob of bytes."""

    def loads(self, blob: bytes) -> D:
        """Decode the blob of bytes into an object."""


@deprecated_class(start_date="Mar 2024")
@add_type_dispatch
class PackageManifest(BaseModel, abc.ABC):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

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


@deprecated_class(start_date="Mar 2024")
@add_type_dispatch
class Packager(BaseModel, abc.ABC):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    Creates a package for a flow.

    A package contains the flow and is typically stored outside of Prefect. To
    facilitate interaction with the package, a manifest is returned that describes how
    to access and use the package.
    """

    type: str

    def base_manifest(self, flow: Flow) -> PackageManifest:
        manifest_cls: Type[BaseModel] = lookup_type(PackageManifest, self.type)
        return manifest_cls.construct(
            type=self.type,
            flow_name=flow.name,
            flow_parameter_schema=parameter_schema(flow.fn),
        )

    @abc.abstractmethod
    async def package(self, flow: Flow) -> "PackageManifest":
        """
        Package a flow and return a manifest describing the created package.
        """
