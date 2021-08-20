import pytest

from unittest.mock import AsyncMock

from prefect.orion.data import write_blob, read_blob, resolve_orion_datadoc
from prefect.orion.schemas.data import DataDocument


class TestReadWriteBlob:
    async def test_write_with_file_schema_writes_to_local_filesystem(self, tmpdir):
        assert (
            await write_blob(scheme="file", path=str(tmpdir.join("test")), blob=b"data")
            is True
        )

        with open(tmpdir.join("test"), "rb") as fp:
            assert fp.read() == b"data"

    async def test_read_with_file_schema_reads_to_local_filesystem(self, tmpdir):

        with open(tmpdir.join("test"), "wb") as fp:
            fp.write(b"data")

        blob = await read_blob(scheme="file", path=str(tmpdir.join("test")))
        assert blob == b"data"


class TestResolveOrionDataDoc:
    async def test_returns_unrecognized_types(self):
        datadoc = DataDocument(encoding="foo", blob=b"hello")
        resolved_datadoc = await resolve_orion_datadoc(datadoc)
        assert datadoc == resolved_datadoc

    @pytest.mark.parametrize("scheme", ["file", "s3"])
    async def test_resolves_location_datadocs(self, monkeypatch, scheme):
        # Mock the file system read
        user_datadoc = DataDocument(encoding="foo", blob=b"hello")
        mock_read_blob = AsyncMock(return_value=user_datadoc.json())
        monkeypatch.setattr("prefect.orion.data.read_blob", mock_read_blob)

        # Build a location datadoc
        datadoc = DataDocument(encoding=scheme, blob=b"this/is/my/path")

        # Resolve it into the user doc from the file system
        resolved_datadoc = await resolve_orion_datadoc(datadoc)
        assert resolved_datadoc == user_datadoc
        mock_read_blob.assert_awaited_once_with(scheme, "this/is/my/path")

    async def test_resolves_orion_datadocs(self, monkeypatch):
        # Mock the file system read
        user_datadoc = DataDocument(encoding="foo", blob=b"hello")
        mock_read_blob = AsyncMock(return_value=user_datadoc.json())
        monkeypatch.setattr("prefect.orion.data.read_blob", mock_read_blob)

        # Build an orion datadoc
        datadoc = DataDocument(
            encoding="orion",
            blob=DataDocument(encoding="file", blob=b"this/is/my/path").json(),
        )

        # Resolve it into the user doc
        resolved_datadoc = await resolve_orion_datadoc(datadoc)
        assert resolved_datadoc == user_datadoc
        mock_read_blob.assert_awaited_once_with("file", "this/is/my/path")
