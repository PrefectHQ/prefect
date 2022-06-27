from pathlib import Path

from pydantic import Field
from typing_extensions import Literal

from prefect.flows import Flow
from prefect.packaging.base import PackageManifest, Packager, Serializer
from prefect.packaging.serializers import SourceSerializer
from prefect.settings import PREFECT_HOME
from prefect.utilities.dispatch import register_type
from prefect.utilities.hashing import stable_hash


@register_type
class FilePackageManifest(PackageManifest):
    type: Literal["file"] = "file"
    serializer: Serializer
    path: Path

    async def unpackage(self) -> Flow:
        with open(self.path, mode="rb") as file:
            content = file.read()
        return self.serializer.loads(content)


@register_type
class FilePackager(Packager):
    """
    This packager stores the flow as a single file.

    By default, the file is the source code of the module the flow is defined in.
    Alternative serialization modes are available in `prefect.packaging.serializers`.
    """

    # TODO: This should use a storage block as a backend for a file system

    type: Literal["file"] = "file"
    serializer: Serializer = Field(default_factory=SourceSerializer)
    basepath: Path = Field(default_factory=lambda: PREFECT_HOME.value() / "storage")

    async def package(self, flow: Flow) -> FilePackageManifest:
        content = self.serializer.dumps(flow)
        key = stable_hash(content)
        path = self.basepath / key

        self.basepath.mkdir(parents=True, exist_ok=True)
        with open(path, mode="wb") as file:
            file.write(content)

        return FilePackageManifest(serializer=self.serializer, path=path)
