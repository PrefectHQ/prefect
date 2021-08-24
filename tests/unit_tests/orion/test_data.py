import pytest

from prefect.utilities.compat import AsyncMock
from prefect.orion.data import (
    FileSystemDataDocument,
    OrionDataDocument,
)
from prefect.orion.schemas.data import DataDocument


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

        # Resolve it into the user doc
        resolved_datadoc = await resolve_orion_datadoc(datadoc)
        assert resolved_datadoc == user_datadoc
        mock_read_blob.assert_awaited_once_with("file", "this/is/my/path")
