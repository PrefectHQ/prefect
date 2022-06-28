import pytest

from prefect.packaging import OrionPackager
from prefect.packaging.orion import OrionPackageManifest
from prefect.packaging.serializers import (
    ImportSerializer,
    PickleSerializer,
    SourceSerializer,
)

from . import howdy


@pytest.mark.parametrize(
    "serializer", [SourceSerializer(), ImportSerializer(), PickleSerializer()]
)
async def test_orion_packager_by_serializer(serializer):
    packager = OrionPackager(serializer=serializer)
    manifest = await packager.package(howdy)

    assert isinstance(manifest, OrionPackageManifest)
    unpackaged_howdy = await manifest.unpackage()
    assert unpackaged_howdy("bro").result() == "howdy, bro!"
