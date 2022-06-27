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
def foo(suffix):
    return f"foo {suffix}"


@pytest.mark.parametrize(
    "serializer", [SourceSerializer(), ImportSerializer(), PickleSerializer()]
)
async def test_orion_packager_by_serializer(serializer):
    packager = OrionPackager(serializer=serializer)
    manifest = await packager.package(foo)

    assert isinstance(manifest, OrionPackageManifest)
    unpackaged_foo = await manifest.unpackage()
    assert unpackaged_foo("bar").result() == "foo bar"
