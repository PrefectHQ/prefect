import pytest

from prefect.deprecated.packaging import OrionPackager
from prefect.deprecated.packaging.orion import OrionPackageManifest
from prefect.deprecated.packaging.serializers import (
    ImportSerializer,
    PickleSerializer,
    SourceSerializer,
)
from prefect.utilities.callables import parameter_schema

from . import howdy


@pytest.mark.parametrize(
    "Serializer", [SourceSerializer, ImportSerializer, PickleSerializer]
)
async def test_orion_packager_by_serializer(Serializer):
    serializer = Serializer()
    packager = OrionPackager(serializer=serializer)
    manifest = await packager.package(howdy)

    assert isinstance(manifest, OrionPackageManifest)
    unpackaged_howdy = await manifest.unpackage()
    assert unpackaged_howdy("bro") == "howdy, bro!"


async def test_packager_sets_manifest_flow_parameter_schema():
    packager = OrionPackager(serializer=SourceSerializer())
    manifest = await packager.package(howdy)
    assert manifest.flow_parameter_schema == parameter_schema(howdy.fn)
