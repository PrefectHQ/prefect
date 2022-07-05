from pydantic import Field
from typing_extensions import Literal

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
    filesystem: ReadableFileSystem

    async def unpackage(self) -> Flow:
        content = await self.filesystem.read_path(self.key)
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

    async def package(self, flow: Flow) -> FilePackageManifest:
        content = self.serializer.dumps(flow)
        key = stable_hash(content)

        await self.filesystem.write_path(key, content)

        return FilePackageManifest(
            flow_name=flow.name,
            serializer=self.serializer,
            filesystem=self.filesystem,
            key=key,
        )
