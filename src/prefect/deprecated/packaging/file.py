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

from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient
from prefect.client.utilities import inject_client
from prefect.deprecated.packaging.base import PackageManifest, Packager, Serializer
from prefect.deprecated.packaging.serializers import SourceSerializer
from prefect.filesystems import LocalFileSystem, ReadableFileSystem, WritableFileSystem
from prefect.flows import Flow
from prefect.settings import PREFECT_HOME
from prefect.utilities.hashing import stable_hash


@deprecated_class(start_date="Mar 2024")
class FilePackageManifest(PackageManifest):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.
    """

    type: str = "file"
    serializer: Serializer
    key: str
    filesystem_id: UUID

    @inject_client
    async def unpackage(self, client: PrefectClient) -> Flow:
        block_document = await client.read_block_document(self.filesystem_id)
        filesystem: ReadableFileSystem = Block._from_block_document(block_document)
        content = await filesystem.read_path(self.key)
        return self.serializer.loads(content)


@deprecated_class(start_date="Mar 2024")
class FilePackager(Packager):
    """
    DEPRECATION WARNING:

    This class is deprecated as of version March 2024 and will not be available after September 2024.

    This packager stores the flow as a single file.

    By default, the file is the source code of the module the flow is defined in.
    Alternative serialization modes are available in `prefect.deprecated.packaging.serializers`.
    """

    type: Literal["file"] = "file"
    serializer: Serializer = Field(default_factory=SourceSerializer)
    filesystem: WritableFileSystem = Field(
        default_factory=lambda: LocalFileSystem(
            basepath=PREFECT_HOME.value() / "storage"
        )
    )

    @inject_client
    async def package(self, flow: Flow, client: "PrefectClient") -> FilePackageManifest:
        content = self.serializer.dumps(flow)
        key = stable_hash(content)

        await self.filesystem.write_path(key, content)

        filesystem_id = (
            self.filesystem._block_document_id
            or await self.filesystem._save(is_anonymous=True)
        )

        return FilePackageManifest(
            **{
                **self.base_manifest(flow).dict(),
                **{
                    "serializer": self.serializer,
                    "filesystem_id": filesystem_id,
                    "key": key,
                },
            }
        )
