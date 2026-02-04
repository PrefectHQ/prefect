import io
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from azure.core.exceptions import ResourceNotFoundError
from prefect_azure.credentials import AzureBlobStorageCredentials
from prefect_azure.experimental.bundles.execute import (
    execute_bundle_from_azure_blob_storage,
)
from pydantic_core import to_json
from pytest import MonkeyPatch

from prefect.runner import Runner


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


@pytest.fixture
def mock_runner(monkeypatch: MonkeyPatch) -> MagicMock:
    """Mock the prefect.runner.Runner class."""
    mock_runner_instance = AsyncMock()
    mock_runner_class = MagicMock(return_value=mock_runner_instance)
    monkeypatch.setattr("prefect.runner.Runner", mock_runner_class)
    return mock_runner_instance


class TestExecuteBundleFromAzureBlobStorage:
    """Tests for the execute_bundle_from_azure_blob_storage function."""

    async def test_execute_bundle_with_credentials_block(
        self, mock_blob_storage_credentials: MagicMock, mock_runner: MagicMock
    ) -> None:
        """Test executing a bundle using a credentials block."""
        container = "test-container"
        key = "test-key"
        credentials_block_name = "test-credentials"
        mock_bundle = {"test": "bundle"}

        # Mock the blob client's download_blob method
        mock_blob_client = (
            mock_blob_storage_credentials.return_value.get_blob_client.return_value
        )
        mock_blob_obj = AsyncMock()
        mock_blob_obj.content_as_bytes = AsyncMock(return_value=b'{"test": "bundle"}')
        mock_blob_client.download_blob = AsyncMock(return_value=mock_blob_obj)

        # Call the function
        await execute_bundle_from_azure_blob_storage(
            container=container,
            key=key,
            azure_blob_storage_credentials_block_name=credentials_block_name,
        )

        # Verify the credentials were loaded from the block
        mock_blob_storage_credentials.load.assert_called_once_with(
            credentials_block_name,
            _sync=False,
        )

        # Verify the blob client was created with the correct container and key
        mock_blob_storage_credentials.return_value.get_blob_client.assert_called_once_with(
            container=container, blob=key
        )

        # Verify the blob was downloaded
        mock_blob_client.download_blob.assert_called_once()

        # Verify the bundle was executed
        mock_runner.execute_bundle.assert_called_once()
        call_args = mock_runner.execute_bundle.call_args[0]
        assert call_args[0] == mock_bundle

    async def test_execute_bundle_with_download_error(
        self, mock_blob_storage_credentials: MagicMock
    ) -> None:
        """Test executing a bundle when the download fails."""
        container = "test-container"
        key = "test-key"
        credentials_block_name = "test-credentials"
        # Mock the blob client's download_blob method to raise an exception
        mock_blob_client = (
            mock_blob_storage_credentials.return_value.get_blob_client.return_value
        )
        mock_blob_client.download_blob.side_effect = ResourceNotFoundError(
            "The specified blob does not exist"
        )

        # Call the function and expect a RuntimeError
        with pytest.raises(
            RuntimeError, match="Failed to download bundle from Azure Blob Storage"
        ):
            await execute_bundle_from_azure_blob_storage(
                container=container,
                key=key,
                azure_blob_storage_credentials_block_name=credentials_block_name,
            )

    async def test_execute_bundle_with_execution_error(
        self, mock_blob_storage_credentials: MagicMock, mock_runner: MagicMock
    ) -> None:
        """Test executing a bundle when the execution fails."""
        container = "test-container"
        key = "test-key"
        credentials_block_name = "test-credentials"
        # Mock the blob client's download_blob method
        mock_blob_client = (
            mock_blob_storage_credentials.return_value.get_blob_client.return_value
        )
        mock_blob_obj = AsyncMock()
        mock_blob_obj.content_as_bytes = AsyncMock(return_value=b'{"test": "bundle"}')
        mock_blob_client.download_blob = AsyncMock(return_value=mock_blob_obj)

        # Mock the runner's execute_bundle method to raise an exception
        mock_runner.execute_bundle.side_effect = Exception("Failed to execute bundle")

        # Call the function and expect a RuntimeError
        with pytest.raises(
            RuntimeError, match="Failed to download bundle from Azure Blob Storage"
        ):
            await execute_bundle_from_azure_blob_storage(
                container=container,
                key=key,
                azure_blob_storage_credentials_block_name=credentials_block_name,
            )


class TestExecuteBundleFromAzureWithFiles:
    """Tests for Azure bundle execution with included files."""

    @pytest.fixture
    def mock_bundle_data_with_files(self) -> dict[str, Any]:
        return {
            "context": "foo",
            "serialize_function": "bar",
            "flow_run": {"name": "buzz", "id": "123"},
            "files_key": "files/abc123.zip",
        }

    @pytest.mark.asyncio
    async def test_execute_with_files_key_downloads_sidecar(
        self,
        mock_bundle_data_with_files: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """When files_key present, sidecar zip is downloaded."""
        download_calls: list[str] = []

        async def mock_download_blob():
            class MockBlobData:
                async def content_as_bytes(self):
                    # Check what's being downloaded based on call count
                    if len(download_calls) == 0:
                        download_calls.append("bundle")
                        return to_json(mock_bundle_data_with_files)
                    else:
                        download_calls.append("files")
                        # Create zip in memory
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w") as zf:
                            zf.writestr("config.yaml", "key: value")
                        return buf.getvalue()

            return MockBlobData()

        mock_blob_client = MagicMock()
        mock_blob_client.download_blob = mock_download_blob

        mock_credentials = MagicMock()
        mock_credentials.get_blob_client.return_value = mock_blob_client

        monkeypatch.setattr(
            "prefect_azure.credentials.AzureBlobStorageCredentials.load",
            AsyncMock(return_value=mock_credentials),
        )

        mock_runner = MagicMock(spec=Runner)
        mock_runner.execute_bundle = AsyncMock()
        monkeypatch.setattr(
            "prefect.runner.Runner", MagicMock(return_value=mock_runner)
        )

        monkeypatch.chdir(tmp_path)

        await execute_bundle_from_azure_blob_storage(
            container="test-container",
            key="bundle.json",
            azure_blob_storage_credentials_block_name="test-creds",
        )

        # Should download both bundle AND sidecar
        assert len(download_calls) == 2
        assert download_calls[0] == "bundle"
        assert download_calls[1] == "files"

    @pytest.mark.asyncio
    async def test_execute_with_files_extracts_to_cwd(
        self,
        mock_bundle_data_with_files: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Files are extracted to working directory."""
        call_count = [0]

        async def mock_download_blob():
            class MockBlobData:
                async def content_as_bytes(self):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return to_json(mock_bundle_data_with_files)
                    else:
                        buf = io.BytesIO()
                        with zipfile.ZipFile(buf, "w") as zf:
                            zf.writestr("data/config.yaml", "key: value")
                        return buf.getvalue()

            return MockBlobData()

        mock_blob_client = MagicMock()
        mock_blob_client.download_blob = mock_download_blob

        mock_credentials = MagicMock()
        mock_credentials.get_blob_client.return_value = mock_blob_client

        monkeypatch.setattr(
            "prefect_azure.credentials.AzureBlobStorageCredentials.load",
            AsyncMock(return_value=mock_credentials),
        )

        mock_runner = MagicMock(spec=Runner)
        mock_runner.execute_bundle = AsyncMock()
        monkeypatch.setattr(
            "prefect.runner.Runner", MagicMock(return_value=mock_runner)
        )

        monkeypatch.chdir(tmp_path)

        await execute_bundle_from_azure_blob_storage(
            container="test-container",
            key="bundle.json",
            azure_blob_storage_credentials_block_name="test-creds",
        )

        # File should be extracted to cwd
        extracted_file = tmp_path / "data" / "config.yaml"
        assert extracted_file.exists()
        assert extracted_file.read_text() == "key: value"
