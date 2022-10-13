from uuid import UUID

from pydantic import Field
from typing_extensions import Literal

from prefect.blocks.core import Block
from prefect.client.orion import OrionClient
from prefect.client.utilities import inject_client
from prefect.filesystems import LocalFileSystem, ReadableFileSystem, WritableFileSystem
from prefect.flows import Flow
from prefect.packaging.base import PackageManifest, Packager, Serializer
from prefect.packaging.serializers import SourceSerializer
from prefect.settings import PREFECT_HOME
from prefect.utilities.hashing import stable_hash


class FilePackageManifest(PackageManifest):
    type: Literal["file"] = "file"
    serializer: Serializer
    key: str
    filesystem_id: UUID

    @inject_client
    async def unpackage(self, client: OrionClient) -> Flow:
        block_document = await client.read_block_document(self.filesystem_id)
        filesystem: ReadableFileSystem = Block._from_block_document(block_document)
        content = await filesystem.read_path(self.key)
        return self.serializer.loads(content)


class FilePackager(Packager):
    """
    This packager stores the flow as a single file.

    By default, the file is the source code of the module the flow is defined in.
    Alternative serialization modes are available in `prefect.packaging.serializers`.
    """

    type: Literal["file"] = "file"
    serializer: Serializer = Field(default_factory=SourceSerializer)
    filesystem: WritableFileSystem = Field(
        default_factory=lambda: LocalFileSystem(
            basepath=PREFECT_HOME.value() / "storage"
        )
    )

    @inject_client
    async def package(self, flow: Flow, client: "OrionClient") -> FilePackageManifest:
        content = self.serializer.dumps(flow)
        key = stable_hash(content)

        await self.filesystem.write_path(key, content)

        filesystem_id = (
            self.filesystem._block_document_id
            or await self.filesystem._save(is_anonymous=True)
        )

        return self.base_manifest(flow).finalize(
            serializer=self.serializer,
            filesystem_id=filesystem_id,
            key=key,
        )
