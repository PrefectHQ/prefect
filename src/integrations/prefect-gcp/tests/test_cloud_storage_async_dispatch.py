"""Tests for async_dispatch migration in prefect-gcp cloud_storage.

These tests verify the critical behavior from issue #15008 where
@sync_compatible would incorrectly return coroutines in sync context.
"""

from io import BytesIO
from typing import Coroutine

import pytest
from prefect_gcp.cloud_storage import (
    GcsBucket,
    acloud_storage_create_bucket,
    acloud_storage_download_blob_as_bytes,
    acloud_storage_download_blob_to_file,
    acloud_storage_upload_blob_from_file,
    acloud_storage_upload_blob_from_string,
    cloud_storage_create_bucket,
    cloud_storage_download_blob_as_bytes,
    cloud_storage_download_blob_to_file,
    cloud_storage_upload_blob_from_file,
    cloud_storage_upload_blob_from_string,
)

from prefect import flow


class TestCloudStorageCreateBucketAsyncDispatch:
    """Tests for cloud_storage_create_bucket migrated from @sync_compatible to @async_dispatch."""

    def test_cloud_storage_create_bucket_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """cloud_storage_create_bucket must return result (not coroutine) in sync context.

        This is a critical regression test for issues #14712 and #14625.
        """

        @flow
        def test_flow():
            result = cloud_storage_create_bucket("test-bucket", gcp_credentials)
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_cloud_storage_create_bucket_async_context_works(
        self, gcp_credentials
    ):
        """cloud_storage_create_bucket should work correctly in async context."""

        @flow
        async def test_flow():
            result = await acloud_storage_create_bucket("test-bucket", gcp_credentials)
            return result

        result = await test_flow()
        assert result is not None

    def test_acloud_storage_create_bucket_is_available(self):
        """acloud_storage_create_bucket should be available for direct async usage."""
        assert callable(acloud_storage_create_bucket)


class TestCloudStorageDownloadBlobAsBytesAsyncDispatch:
    """Tests for cloud_storage_download_blob_as_bytes migrated from @sync_compatible to @async_dispatch."""

    def test_cloud_storage_download_blob_as_bytes_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """cloud_storage_download_blob_as_bytes must return bytes (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = cloud_storage_download_blob_as_bytes(
                "test-bucket", "test-blob", gcp_credentials
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert isinstance(result, bytes)

    async def test_cloud_storage_download_blob_as_bytes_async_context_works(
        self, gcp_credentials
    ):
        """cloud_storage_download_blob_as_bytes should work correctly in async context."""

        @flow
        async def test_flow():
            result = await acloud_storage_download_blob_as_bytes(
                "test-bucket", "test-blob", gcp_credentials
            )
            return result

        result = await test_flow()
        assert isinstance(result, bytes)

    def test_acloud_storage_download_blob_as_bytes_is_available(self):
        """acloud_storage_download_blob_as_bytes should be available for direct async usage."""
        assert callable(acloud_storage_download_blob_as_bytes)


class TestCloudStorageDownloadBlobToFileAsyncDispatch:
    """Tests for cloud_storage_download_blob_to_file migrated from @sync_compatible to @async_dispatch."""

    def test_cloud_storage_download_blob_to_file_sync_context_returns_value_not_coroutine(
        self, gcp_credentials, tmp_path
    ):
        """cloud_storage_download_blob_to_file must return path (not coroutine) in sync context."""
        output_file = tmp_path / "output.txt"

        @flow
        def test_flow():
            result = cloud_storage_download_blob_to_file(
                "test-bucket", "test-blob", str(output_file), gcp_credentials
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_cloud_storage_download_blob_to_file_async_context_works(
        self, gcp_credentials, tmp_path
    ):
        """cloud_storage_download_blob_to_file should work correctly in async context."""
        output_file = tmp_path / "output.txt"

        @flow
        async def test_flow():
            result = await acloud_storage_download_blob_to_file(
                "test-bucket", "test-blob", str(output_file), gcp_credentials
            )
            return result

        result = await test_flow()
        assert result is not None

    def test_acloud_storage_download_blob_to_file_is_available(self):
        """acloud_storage_download_blob_to_file should be available for direct async usage."""
        assert callable(acloud_storage_download_blob_to_file)


class TestCloudStorageUploadBlobFromStringAsyncDispatch:
    """Tests for cloud_storage_upload_blob_from_string migrated from @sync_compatible to @async_dispatch."""

    def test_cloud_storage_upload_blob_from_string_sync_context_returns_value_not_coroutine(
        self, gcp_credentials
    ):
        """cloud_storage_upload_blob_from_string must return result (not coroutine) in sync context."""

        @flow
        def test_flow():
            result = cloud_storage_upload_blob_from_string(
                "test data", "test-bucket", "test-blob", gcp_credentials
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_cloud_storage_upload_blob_from_string_async_context_works(
        self, gcp_credentials
    ):
        """cloud_storage_upload_blob_from_string should work correctly in async context."""

        @flow
        async def test_flow():
            result = await acloud_storage_upload_blob_from_string(
                "test data", "test-bucket", "test-blob", gcp_credentials
            )
            return result

        result = await test_flow()
        assert result is not None

    def test_acloud_storage_upload_blob_from_string_is_available(self):
        """acloud_storage_upload_blob_from_string should be available for direct async usage."""
        assert callable(acloud_storage_upload_blob_from_string)


class TestCloudStorageUploadBlobFromFileAsyncDispatch:
    """Tests for cloud_storage_upload_blob_from_file migrated from @sync_compatible to @async_dispatch."""

    def test_cloud_storage_upload_blob_from_file_sync_context_returns_value_not_coroutine(
        self, gcp_credentials, tmp_path
    ):
        """cloud_storage_upload_blob_from_file must return result (not coroutine) in sync context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test data")

        @flow
        def test_flow():
            result = cloud_storage_upload_blob_from_file(
                str(test_file), "test-bucket", "test-blob", gcp_credentials
            )
            assert not isinstance(result, Coroutine), "sync context returned coroutine"
            return result

        result = test_flow()
        assert result is not None

    async def test_cloud_storage_upload_blob_from_file_async_context_works(
        self, gcp_credentials, tmp_path
    ):
        """cloud_storage_upload_blob_from_file should work correctly in async context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test data")

        @flow
        async def test_flow():
            result = await acloud_storage_upload_blob_from_file(
                str(test_file), "test-bucket", "test-blob", gcp_credentials
            )
            return result

        result = await test_flow()
        assert result is not None

    def test_acloud_storage_upload_blob_from_file_is_available(self):
        """acloud_storage_upload_blob_from_file should be available for direct async usage."""
        assert callable(acloud_storage_upload_blob_from_file)


class TestGcsBucketReadPathAsyncDispatch:
    """Tests for GcsBucket.read_path migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_read_path_sync_context_returns_value_not_coroutine(self, gcs_bucket):
        """read_path must return bytes (not coroutine) in sync context."""
        result = gcs_bucket.read_path("test-path")
        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, bytes)

    async def test_read_path_async_context_works(self, gcs_bucket):
        """read_path should work correctly in async context."""
        result = await gcs_bucket.aread_path("test-path")
        assert isinstance(result, bytes)

    def test_aread_path_is_available(self, gcs_bucket):
        """aread_path should be available for direct async usage."""
        assert hasattr(gcs_bucket, "aread_path")
        assert callable(gcs_bucket.aread_path)


class TestGcsBucketWritePathAsyncDispatch:
    """Tests for GcsBucket.write_path migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_write_path_sync_context_returns_value_not_coroutine(self, gcs_bucket):
        """write_path must return path (not coroutine) in sync context."""
        result = gcs_bucket.write_path("test-path", b"test content")
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_write_path_async_context_works(self, gcs_bucket):
        """write_path should work correctly in async context."""
        result = await gcs_bucket.awrite_path("test-path", b"test content")
        assert result is not None

    def test_awrite_path_is_available(self, gcs_bucket):
        """awrite_path should be available for direct async usage."""
        assert hasattr(gcs_bucket, "awrite_path")
        assert callable(gcs_bucket.awrite_path)


class TestGcsBucketGetBucketAsyncDispatch:
    """Tests for GcsBucket.get_bucket migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_get_bucket_sync_context_returns_value_not_coroutine(self, gcs_bucket):
        """get_bucket must return bucket (not coroutine) in sync context."""
        result = gcs_bucket.get_bucket()
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_get_bucket_async_context_works(self, gcs_bucket):
        """get_bucket should work correctly in async context."""
        result = await gcs_bucket.aget_bucket()
        assert result is not None

    def test_aget_bucket_is_available(self, gcs_bucket):
        """aget_bucket should be available for direct async usage."""
        assert hasattr(gcs_bucket, "aget_bucket")
        assert callable(gcs_bucket.aget_bucket)


class TestGcsBucketListBlobsAsyncDispatch:
    """Tests for GcsBucket.list_blobs migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_list_blobs_sync_context_returns_value_not_coroutine(self, gcs_bucket):
        """list_blobs must return list (not coroutine) in sync context."""
        result = gcs_bucket.list_blobs()
        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, list)

    async def test_list_blobs_async_context_works(self, gcs_bucket):
        """list_blobs should work correctly in async context."""
        result = await gcs_bucket.alist_blobs()
        assert isinstance(result, list)

    def test_alist_blobs_is_available(self, gcs_bucket):
        """alist_blobs should be available for direct async usage."""
        assert hasattr(gcs_bucket, "alist_blobs")
        assert callable(gcs_bucket.alist_blobs)


class TestGcsBucketListFoldersAsyncDispatch:
    """Tests for GcsBucket.list_folders migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_list_folders_sync_context_returns_value_not_coroutine(self, gcs_bucket):
        """list_folders must return list (not coroutine) in sync context."""
        result = gcs_bucket.list_folders()
        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        assert isinstance(result, list)

    async def test_list_folders_async_context_works(self, gcs_bucket):
        """list_folders should work correctly in async context."""
        result = await gcs_bucket.alist_folders()
        assert isinstance(result, list)

    def test_alist_folders_is_available(self, gcs_bucket):
        """alist_folders should be available for direct async usage."""
        assert hasattr(gcs_bucket, "alist_folders")
        assert callable(gcs_bucket.alist_folders)


class TestGcsBucketDownloadObjectToPathAsyncDispatch:
    """Tests for GcsBucket.download_object_to_path migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(
            bucket="test-bucket",
            gcp_credentials=gcp_credentials,
            bucket_folder="base_folder",
        )

    def test_download_object_to_path_sync_context_returns_value_not_coroutine(
        self, gcs_bucket, tmp_path
    ):
        """download_object_to_path must return path (not coroutine) in sync context."""
        to_path = tmp_path / "downloaded.txt"
        result = gcs_bucket.download_object_to_path("nested_blob.txt", to_path)
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_download_object_to_path_async_context_works(
        self, gcs_bucket, tmp_path
    ):
        """download_object_to_path should work correctly in async context."""
        to_path = tmp_path / "downloaded.txt"
        result = await gcs_bucket.adownload_object_to_path("nested_blob.txt", to_path)
        assert result is not None

    def test_adownload_object_to_path_is_available(self, gcs_bucket):
        """adownload_object_to_path should be available for direct async usage."""
        assert hasattr(gcs_bucket, "adownload_object_to_path")
        assert callable(gcs_bucket.adownload_object_to_path)


class TestGcsBucketDownloadObjectToFileObjectAsyncDispatch:
    """Tests for GcsBucket.download_object_to_file_object migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(
            bucket="test-bucket",
            gcp_credentials=gcp_credentials,
            bucket_folder="base_folder",
        )

    def test_download_object_to_file_object_sync_context_returns_value_not_coroutine(
        self, gcs_bucket
    ):
        """download_object_to_file_object must return file object (not coroutine) in sync context."""
        file_obj = BytesIO()
        result = gcs_bucket.download_object_to_file_object("nested_blob.txt", file_obj)
        assert not isinstance(result, Coroutine), "sync context returned coroutine"
        # Returns the file object with content written to it
        assert result is file_obj

    async def test_download_object_to_file_object_async_context_works(self, gcs_bucket):
        """download_object_to_file_object should work correctly in async context."""
        file_obj = BytesIO()
        result = await gcs_bucket.adownload_object_to_file_object(
            "nested_blob.txt", file_obj
        )
        # Returns the file object with content written to it
        assert result is file_obj

    def test_adownload_object_to_file_object_is_available(self, gcs_bucket):
        """adownload_object_to_file_object should be available for direct async usage."""
        assert hasattr(gcs_bucket, "adownload_object_to_file_object")
        assert callable(gcs_bucket.adownload_object_to_file_object)


class TestGcsBucketDownloadFolderToPathAsyncDispatch:
    """Tests for GcsBucket.download_folder_to_path migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_download_folder_to_path_sync_context_returns_value_not_coroutine(
        self, gcs_bucket, tmp_path
    ):
        """download_folder_to_path must return path (not coroutine) in sync context."""
        result = gcs_bucket.download_folder_to_path("base_folder", tmp_path)
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_download_folder_to_path_async_context_works(
        self, gcs_bucket, tmp_path
    ):
        """download_folder_to_path should work correctly in async context."""
        result = await gcs_bucket.adownload_folder_to_path("base_folder", tmp_path)
        assert result is not None

    def test_adownload_folder_to_path_is_available(self, gcs_bucket):
        """adownload_folder_to_path should be available for direct async usage."""
        assert hasattr(gcs_bucket, "adownload_folder_to_path")
        assert callable(gcs_bucket.adownload_folder_to_path)


class TestGcsBucketUploadFromPathAsyncDispatch:
    """Tests for GcsBucket.upload_from_path migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(
            bucket="test-bucket",
            gcp_credentials=gcp_credentials,
            bucket_folder="base_folder",
        )

    def test_upload_from_path_sync_context_returns_value_not_coroutine(
        self, gcs_bucket, tmp_path
    ):
        """upload_from_path must return path (not coroutine) in sync context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = gcs_bucket.upload_from_path(test_file)
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_upload_from_path_async_context_works(self, gcs_bucket, tmp_path):
        """upload_from_path should work correctly in async context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = await gcs_bucket.aupload_from_path(test_file)
        assert result is not None

    def test_aupload_from_path_is_available(self, gcs_bucket):
        """aupload_from_path should be available for direct async usage."""
        assert hasattr(gcs_bucket, "aupload_from_path")
        assert callable(gcs_bucket.aupload_from_path)


class TestGcsBucketUploadFromFileObjectAsyncDispatch:
    """Tests for GcsBucket.upload_from_file_object migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(
            bucket="test-bucket",
            gcp_credentials=gcp_credentials,
            bucket_folder="base_folder",
        )

    def test_upload_from_file_object_sync_context_returns_value_not_coroutine(
        self, gcs_bucket
    ):
        """upload_from_file_object must return path (not coroutine) in sync context."""
        file_obj = BytesIO(b"test content")
        result = gcs_bucket.upload_from_file_object(file_obj, "test-blob")
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_upload_from_file_object_async_context_works(self, gcs_bucket):
        """upload_from_file_object should work correctly in async context."""
        file_obj = BytesIO(b"test content")
        result = await gcs_bucket.aupload_from_file_object(file_obj, "test-blob")
        assert result is not None

    def test_aupload_from_file_object_is_available(self, gcs_bucket):
        """aupload_from_file_object should be available for direct async usage."""
        assert hasattr(gcs_bucket, "aupload_from_file_object")
        assert callable(gcs_bucket.aupload_from_file_object)


class TestGcsBucketUploadFromFolderAsyncDispatch:
    """Tests for GcsBucket.upload_from_folder migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_upload_from_folder_sync_context_returns_value_not_coroutine(
        self, gcs_bucket, tmp_path
    ):
        """upload_from_folder must return path (not coroutine) in sync context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = gcs_bucket.upload_from_folder(tmp_path)
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_upload_from_folder_async_context_works(self, gcs_bucket, tmp_path):
        """upload_from_folder should work correctly in async context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = await gcs_bucket.aupload_from_folder(tmp_path)
        assert result is not None

    def test_aupload_from_folder_is_available(self, gcs_bucket):
        """aupload_from_folder should be available for direct async usage."""
        assert hasattr(gcs_bucket, "aupload_from_folder")
        assert callable(gcs_bucket.aupload_from_folder)


class TestGcsBucketGetDirectoryAsyncDispatch:
    """Tests for GcsBucket.get_directory migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_get_directory_sync_context_returns_value_not_coroutine(
        self, gcs_bucket, tmp_path
    ):
        """get_directory must return path (not coroutine) in sync context."""
        result = gcs_bucket.get_directory(local_path=str(tmp_path))
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_get_directory_async_context_works(self, gcs_bucket, tmp_path):
        """get_directory should work correctly in async context."""
        result = await gcs_bucket.aget_directory(local_path=str(tmp_path))
        assert result is not None

    def test_aget_directory_is_available(self, gcs_bucket):
        """aget_directory should be available for direct async usage."""
        assert hasattr(gcs_bucket, "aget_directory")
        assert callable(gcs_bucket.aget_directory)


class TestGcsBucketPutDirectoryAsyncDispatch:
    """Tests for GcsBucket.put_directory migrated from @sync_compatible to @async_dispatch."""

    @pytest.fixture
    def gcs_bucket(self, gcp_credentials):
        return GcsBucket(bucket="test-bucket", gcp_credentials=gcp_credentials)

    def test_put_directory_sync_context_returns_value_not_coroutine(
        self, gcs_bucket, tmp_path
    ):
        """put_directory must return count (not coroutine) in sync context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = gcs_bucket.put_directory(local_path=str(tmp_path))
        assert not isinstance(result, Coroutine), "sync context returned coroutine"

    async def test_put_directory_async_context_works(self, gcs_bucket, tmp_path):
        """put_directory should work correctly in async context."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        result = await gcs_bucket.aput_directory(local_path=str(tmp_path))
        assert result is not None

    def test_aput_directory_is_available(self, gcs_bucket):
        """aput_directory should be available for direct async usage."""
        assert hasattr(gcs_bucket, "aput_directory")
        assert callable(gcs_bucket.aput_directory)
