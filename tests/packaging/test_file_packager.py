import pytest

from prefect.packaging import FilePackager
from prefect.packaging.file import FilePackageManifest
from prefect.packaging.serializers import (
    ImportSerializer,
    PickleSerializer,
    SourceSerializer,
)
from prefect.utilities.callables import parameter_schema

from . import howdy


@pytest.mark.parametrize(
    "serializer", [SourceSerializer(), ImportSerializer(), PickleSerializer()]
)
async def test_file_packager_by_serializer(serializer):
    packager = FilePackager(serializer=serializer)
    manifest = await packager.package(howdy)

    assert isinstance(manifest, FilePackageManifest)
    unpackaged_howdy = await manifest.unpackage()
    assert unpackaged_howdy("bro") == "howdy, bro!"


async def test_packager_sets_manifest_flow_parameter_schema():
    packager = FilePackager(serializer=SourceSerializer())
    manifest = await packager.package(howdy)
    assert manifest.flow_parameter_schema == parameter_schema(howdy.fn)
