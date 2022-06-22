from pathlib import Path

from pydantic import Field

from prefect.flows import Flow
from prefect.packaging.base import PackageManifest, Serializer
from prefect.packaging.serializers import PickleSerializer
from prefect.utilities.hashing import stable_hash


class FilePackager:
    serializer: Serializer = Field(default_factory=PickleSerializer)

    async def package(self, flow: Flow) -> "FilePackageManifest":
        """
        Package a flow as a file.
        """
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
