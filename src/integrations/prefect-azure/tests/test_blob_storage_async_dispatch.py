"""Tests for the async_dispatch migration in prefect-azure blob storage.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

from io import BytesIO
from typing import Coroutine

from prefect_azure.blob_storage import AzureBlobStorageContainer

from prefect import flow


def _container(mock_blob_storage_credentials) -> AzureBlobStorageContainer:
    return AzureBlobStorageContainer(
        container_name="container",
        credentials=mock_blob_storage_credentials,
    )


class TestReadPathAsyncDispatch:
    def test_read_path_sync_context_returns_bytes_not_coroutine(
        self, mock_blob_storage_credentials
    ):
        """read_path must return bytes (not a coroutine) in sync context."""

        @flow
        def test_flow():
            container = _container(mock_blob_storage_credentials)
            result = container.read_path("prefect.txt")
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        assert test_flow() == b"prefect_works"

    async def test_aread_path_async_context_works(self, mock_blob_storage_credentials):
        """aread_path should work correctly in async context."""

        @flow
        async def test_flow():
            container = _container(mock_blob_storage_credentials)
            return await container.aread_path("prefect.txt")

        assert await test_flow() == b"prefect_works"

    def test_aread_path_is_available(self, mock_blob_storage_credentials):
        container = _container(mock_blob_storage_credentials)
        assert hasattr(container, "aread_path")
        assert callable(container.aread_path)


class TestWritePathAsyncDispatch:
    def test_write_path_sync_context_does_not_return_coroutine(
        self, mock_blob_storage_credentials
    ):
        """write_path must not return a coroutine in sync context."""

        @flow
        def test_flow():
            container = _container(mock_blob_storage_credentials)
            result = container.write_path("new-blob.txt", content=b"hello")
            assert not isinstance(result, Coroutine), "sync context returned coroutine"

        test_flow()

    async def test_awrite_path_async_context_works(self, mock_blob_storage_credentials):
        @flow
        async def test_flow():
            container = _container(mock_blob_storage_credentials)
            await container.awrite_path("another-blob.txt", content=b"hello")

        await test_flow()


class TestDownloadObjectToPathAsyncDispatch:
    def test_download_object_to_path_sync_context_returns_path_not_coroutine(
        self, mock_blob_storage_credentials, tmp_path
    ):
        @flow
        def test_flow():
            container = _container(mock_blob_storage_credentials)
            result = container.download_object_to_path(
                "prefect.txt", tmp_path / "file.txt"
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result == tmp_path / "file.txt"
        assert (tmp_path / "file.txt").read_bytes() == b"prefect_works"

    async def test_adownload_object_to_path_async_context_works(
        self, mock_blob_storage_credentials, tmp_path
    ):
        @flow
        async def test_flow():
            container = _container(mock_blob_storage_credentials)
            return await container.adownload_object_to_path(
                "prefect.txt", tmp_path / "file.txt"
            )

        result = await test_flow()
        assert result == tmp_path / "file.txt"
        assert (tmp_path / "file.txt").read_bytes() == b"prefect_works"


class TestDownloadObjectToFileObjectAsyncDispatch:
    def test_download_to_file_object_sync_context_not_coroutine(
        self, mock_blob_storage_credentials
    ):
        @flow
        def test_flow():
            container = _container(mock_blob_storage_credentials)
            file_obj = BytesIO()
            result = container.download_object_to_file_object("prefect.txt", file_obj)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return file_obj.getvalue()

        assert test_flow() == b"prefect_works"


def test_all_async_methods_are_available(mock_blob_storage_credentials):
    """Every migrated method exposes an `a`-prefixed async counterpart."""
    container = _container(mock_blob_storage_credentials)
    for name in (
        "download_folder_to_path",
        "download_object_to_file_object",
        "download_object_to_path",
        "upload_from_file_object",
        "upload_from_path",
        "upload_from_folder",
        "get_directory",
        "put_directory",
        "read_path",
        "write_path",
        "list_blobs",
    ):
        assert hasattr(container, f"a{name}"), f"missing a{name}"
        assert callable(getattr(container, f"a{name}"))
        # the sync wrapper still exposes `.aio` for backwards compatibility
        assert hasattr(getattr(container, name), "aio")
