import pytest

from prefect import flow
from prefect.packaging import OrionPackager
from prefect.packaging.orion import OrionPackageManifest
from prefect.packaging.serializers import (
    ImportSerializer,
    PickleSerializer,
    SourceSerializer,
)


@flow
def towdy(name):
    return f"towdy {name}"


@pytest.mark.parametrize(
    "serializer", [SourceSerializer(), ImportSerializer(), PickleSerializer()]
)
async def test_orion_packager_by_serializer(serializer):
    packager = OrionPackager(serializer=serializer)
    manifest = await packager.package(towdy)

    assert isinstance(manifest, OrionPackageManifest)
    unpackaged_towdy = await manifest.unpackage()
    assert unpackaged_towdy("bro").result() == "towdy bro"
