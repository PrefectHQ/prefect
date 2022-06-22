from typing import TYPE_CHECKING

from pydantic import Field

from prefect.packaging.base import PackageManifest, Serializer
from prefect.packaging.serializers import SourceSerializer
from prefect.utilities.hashing import stable_hash

if TYPE_CHECKING:
    from prefect.deployments import FlowSource


class FilePackageManifest(PackageManifest):
    pass


class FilePackager:
    serializer: Serializer = Field(default_factory=SourceSerializer)

    async def package(self, flow: "FlowSource") -> FilePackageManifest:
        """
        Package a flow as a file.
        """
        content = self.serializer.dumps(flow)
        key = stable_hash(content)
        path = self.basepath / key

        with open(path, mode="wb") as file:
            file.write(content)

        return str(path).encode()
