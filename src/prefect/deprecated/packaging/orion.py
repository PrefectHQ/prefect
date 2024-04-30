"""
DEPRECATION WARNING:
This module is deprecated as of March 2024 and will not be available after September 2024.
"""

from uuid import UUID

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from typing_extensions import Literal

from prefect.blocks.system import JSON
from prefect.client.orchestration import PrefectClient
from prefect.client.utilities import inject_client
from prefect.deprecated.packaging.base import PackageManifest, Packager, Serializer
from prefect.deprecated.packaging.serializers import SourceSerializer
from prefect.flows import Flow


@deprecated_class(start_date="Mar 2024")
class OrionPackageManifest(PackageManifest):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.
    """

    type: str = "orion"
    serializer: Serializer
    block_document_id: UUID

    @inject_client
    async def unpackage(self, client: PrefectClient) -> Flow:
        document = await client.read_block_document(self.block_document_id)
        block = JSON._from_block_document(document)
        serialized_flow: str = block.value["flow"]
        # Cast to bytes before deserialization
        return self.serializer.loads(serialized_flow.encode())


@deprecated_class(start_date="Mar 2024")
class OrionPackager(Packager):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    This packager stores the flow as an anonymous JSON block in the Prefect database.
    The content of the block are encrypted at rest.

    By default, the content is the source code of the module the flow is defined in.
    Alternative serialization modes are available in `prefect.deprecated.packaging.serializers`.
    """

    type: Literal["orion"] = "orion"
    serializer: Serializer = Field(default_factory=SourceSerializer)

    async def package(self, flow: Flow) -> OrionPackageManifest:
        """
        Package a flow in the Prefect database as an anonymous block.
        """
        block_document_id = await JSON(
            value={"flow": self.serializer.dumps(flow)}
        )._save(is_anonymous=True)

        return OrionPackageManifest(
            **{
                **self.base_manifest(flow).dict(),
                **{
                    "serializer": self.serializer,
                    "block_document_id": block_document_id,
                },
            }
        )
