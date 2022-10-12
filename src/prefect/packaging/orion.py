from uuid import UUID

from pydantic import Field
from typing_extensions import Literal

from prefect.blocks.system import JSON
from prefect.client.orion import OrionClient
from prefect.client.utilities import inject_client
from prefect.flows import Flow
from prefect.packaging.base import PackageManifest, Packager, Serializer
from prefect.packaging.serializers import SourceSerializer


class OrionPackageManifest(PackageManifest):
    type: Literal["orion"] = "orion"
    serializer: Serializer
    block_document_id: UUID

    @inject_client
    async def unpackage(self, client: OrionClient) -> Flow:
        document = await client.read_block_document(self.block_document_id)
        block = JSON._from_block_document(document)
        serialized_flow: str = block.value["flow"]
        # Cast to bytes before deserialization
        return self.serializer.loads(serialized_flow.encode())


class OrionPackager(Packager):
    """
    This packager stores the flow as an anonymous JSON block in the Orion database.
    The content of the block are encrypted at rest.

    By default, the content is the source code of the module the flow is defined in.
    Alternative serialization modes are available in `prefect.packaging.serializers`.
    """

    type: Literal["orion"] = "orion"
    serializer: Serializer = Field(default_factory=SourceSerializer)

    async def package(self, flow: Flow) -> OrionPackageManifest:
        """
        Package a flow in the Orion database as an anonymous block.
        """
        block_document_id = await JSON(
            value={"flow": self.serializer.dumps(flow)}
        )._save(is_anonymous=True)

        return self.base_manifest(flow).finalize(
            serializer=self.serializer,
            block_document_id=block_document_id,
        )
