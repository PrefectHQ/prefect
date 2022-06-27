import pytest

from prefect import flow
from prefect.packaging import FilePackager
from prefect.packaging.file import FilePackageManifest
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
async def test_file_packager_by_serializer(serializer):
    packager = FilePackager(serializer=serializer)
    manifest = await packager.package(foo)

    assert isinstance(manifest, FilePackageManifest)
    unpackaged_foo = await manifest.unpackage()
    assert unpackaged_foo("bar").result() == "foo bar"
