from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import ResourceExistsError
from prefect_azure.credentials import AzureBlobStorageCredentials
from prefect_azure.experimental.bundles.upload import (
    upload_bundle_to_azure_blob_storage,
)
from pytest import MonkeyPatch


@pytest.fixture
def tmp_bundle_file(tmp_path: Path) -> Path:
    bundle_file = tmp_path / "test_bundle.zip"
    bundle_file.write_bytes(b"test bundle content")
    return bundle_file


@pytest.fixture
def mock_blob_storage_credentials(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the AzureBlobStorageCredentials class."""
    mock_credentials = MagicMock(
        spec=AzureBlobStorageCredentials, name="mock-azure-blob-storage-credentials"
    )
    monkeypatch.setattr(
        "prefect_azure.credentials.AzureBlobStorageCredentials",
        mock_credentials,
    )
    mock_credentials.load = AsyncMock(return_value=mock_credentials.return_value)

    return mock_credentials


class TestUploadBundleToAzureBlobStorage:
    """Tests for the upload_bundle_to_azure_blob_storage function."""

    async def test_upload_bundle_with_credentials_block(
        self, tmp_bundle_file: Path, mock_blob_storage_credentials: MagicMock
    ) -> None:
        """Test uploading a bundle using a credentials block."""
        container = "test-container"
        key = "test-key"
        credentials_block_name = "test-credentials"

        # Mock the container client's upload_blob method
        mock_container_client = (
            mock_blob_storage_credentials.return_value.get_container_client.return_value
        )
        mock_container_client.upload_blob = AsyncMock()

        # Call the function
        result = await upload_bundle_to_azure_blob_storage(
            local_filepath=tmp_bundle_file,
            container=container,
            key=key,
            azure_blob_storage_credentials_block_name=credentials_block_name,
        )

        # Verify the result
        assert result == {"container": container, "key": key}

        # Verify the credentials were loaded from the block
        mock_blob_storage_credentials.load.assert_called_once_with(
            credentials_block_name,
            _sync=False,
        )

        # Verify the container client was created with the correct container
        mock_blob_storage_credentials.return_value.get_container_client.assert_called_once_with(
            container=container
        )

        # Verify the blob was uploaded
        mock_container_client.upload_blob.assert_called_once()

    async def test_upload_bundle_with_nonexistent_file(self, tmp_path: Path) -> None:
        """Test uploading a bundle with a nonexistent file."""
        nonexistent_file = tmp_path / "nonexistent.zip"
        container = "test-container"
        key = "test-key"
        credentials_block_name = "test-credentials"

        # Call the function and expect a ValueError
        with pytest.raises(
            ValueError, match=f"Bundle file not found: {nonexistent_file}"
        ):
            await upload_bundle_to_azure_blob_storage(
                local_filepath=nonexistent_file,
                container=container,
                key=key,
                azure_blob_storage_credentials_block_name=credentials_block_name,
            )

    async def test_upload_bundle_with_upload_error(
        self, tmp_bundle_file: Path, mock_blob_storage_credentials: MagicMock
    ) -> None:
        """Test uploading a bundle when the upload fails."""
        container = "test-container"
        key = "test-key"
        credentials_block_name = "test-credentials"

        # Mock the container client's upload_blob method to raise an exception
        mock_container_client = (
            mock_blob_storage_credentials.return_value.get_container_client.return_value
        )
        mock_container_client.upload_blob.side_effect = ResourceExistsError(
            "Blob already exists"
        )

        # Call the function and expect a RuntimeError
        with pytest.raises(
            RuntimeError, match="Failed to upload bundle to Azure Blob Storage"
        ):
            await upload_bundle_to_azure_blob_storage(
                local_filepath=tmp_bundle_file,
                container=container,
                key=key,
                azure_blob_storage_credentials_block_name=credentials_block_name,
            )

    async def test_upload_bundle_with_empty_key(
        self, tmp_bundle_file: Path, mock_blob_storage_credentials: MagicMock
    ) -> None:
        """Test uploading a bundle with an empty key (should use the filename)."""
        container = "test-container"
        key = ""  # Empty key
        credentials_block_name = "test-credentials"
        # Mock the container client's upload_blob method
        mock_container_client = (
            mock_blob_storage_credentials.return_value.get_container_client.return_value
        )
        mock_container_client.upload_blob = AsyncMock()

        # Call the function
        result = await upload_bundle_to_azure_blob_storage(
            local_filepath=tmp_bundle_file,
            container=container,
            key=key,
            azure_blob_storage_credentials_block_name=credentials_block_name,
        )

        # Verify the result uses the filename as the key
        assert result == {"container": container, "key": tmp_bundle_file.name}

        # Verify the blob was uploaded with the filename as the key
        mock_container_client.upload_blob.assert_called_once()
        call_args = mock_container_client.upload_blob.call_args[0]
        assert call_args[0] == tmp_bundle_file.name
