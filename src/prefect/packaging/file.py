from pathlib import Path

from pydantic import Field

from prefect.flows import Flow
from prefect.packaging.base import PackageManifest, Serializer
from prefect.packaging.serializers import SourceSerializer
from prefect.utilities.hashing import stable_hash


class FilePackager:
    """
    This packager stores the flow as a single file.

    By default, the file is the source code of the module the flow is defined in.
    Alternative serialization modes are available in `prefect.packaging.serializers`.
    """

    serializer: Serializer = Field(default_factory=SourceSerializer)

    async def package(self, flow: Flow) -> "FilePackageManifest":
        content = self.serializer.dumps(flow)
        key = stable_hash(content)
        path = self.basepath / key

        with open(path, mode="wb") as file:
            file.write(content)

        return FilePackageManifest(serializer=self.serializer, path=path)

    @staticmethod
    def unpackage(manifest: "FilePackageManifest") -> Flow:
        with open(manifest.path, mode="rb") as file:
            content = file.read()
        return manifest.serializer.loads(content)


class FilePackageManifest(PackageManifest):
    __packager__ = FilePackager

    serializer: Serializer
    path: Path
