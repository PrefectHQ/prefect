from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from prefect_gcp.experimental.bundles.execute import execute_bundle_from_gcs
from pydantic_core import to_json

from prefect.runner import Runner


@pytest.fixture
def mock_bundle_data() -> dict[str, Any]:
    return {
        "context": "foo",
        "serialize_function": "bar",
        "flow_run": {"name": "buzz", "id": "123"},
    }


def test_execute_bundle_from_gcs_success(
    gcp_credentials: MagicMock,
    mock_bundle_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock the GcpCredentials.load method
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials.load",
        MagicMock(return_value=gcp_credentials),
    )

    # Mock the Runner and its execute_bundle method
    mock_runner = MagicMock(spec=Runner)
    monkeypatch.setattr("prefect.runner.Runner", MagicMock(return_value=mock_runner))

    # Call the function
    bucket = "test-bucket"
    key = "test-key.json"

    def mock_download_to_file(path: str) -> None:
        Path(path).write_bytes(to_json(mock_bundle_data))

    # wow, i love mocking so much
    gcp_credentials.get_cloud_storage_client.return_value.bucket.return_value.blob.return_value.download_to_file.side_effect = mock_download_to_file

    execute_bundle_from_gcs(
        bucket=bucket,
        key=key,
        gcp_credentials_block_name="test-credentials",
    )

    # Verify the GCS client was called correctly
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket.assert_called_once_with(bucket)
    gcs_client.bucket(bucket).blob.assert_called_once_with(key)
    gcs_client.bucket(bucket).blob(key).download_to_file.assert_called_once()

    # Verify the Runner was called correctly
    mock_runner.execute_bundle.assert_called_once_with(mock_bundle_data)


def test_execute_bundle_from_gcs_with_default_credentials(
    gcp_credentials: MagicMock,
    mock_bundle_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock the GcpCredentials constructor
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials",
        MagicMock(return_value=gcp_credentials),
    )

    # Mock the Runner and its execute_bundle method
    mock_runner = MagicMock(spec=Runner)
    monkeypatch.setattr("prefect.runner.Runner", MagicMock(return_value=mock_runner))

    # Call the function
    bucket = "test-bucket"
    key = "test-key.json"

    def mock_download_to_file(path: str) -> None:
        Path(path).write_bytes(to_json(mock_bundle_data))

    # Set up the mock for download_to_file
    gcp_credentials.get_cloud_storage_client.return_value.bucket.return_value.blob.return_value.download_to_file.side_effect = mock_download_to_file

    execute_bundle_from_gcs(
        bucket=bucket,
        key=key,
    )

    # Verify the GCS client was called correctly
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket.assert_called_once_with(bucket)
    gcs_client.bucket(bucket).blob.assert_called_once_with(key)
    gcs_client.bucket(bucket).blob(key).download_to_file.assert_called_once()

    # Verify the Runner was called correctly
    mock_runner.execute_bundle.assert_called_once_with(mock_bundle_data)


def test_execute_bundle_from_gcs_download_failure(
    gcp_credentials: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock the GcpCredentials.load method
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials.load",
        MagicMock(return_value=gcp_credentials),
    )

    # Call the function
    bucket = "test-bucket"
    key = "test-key.json"

    # Mock the GCS client to raise an exception
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket(bucket).blob(key).download_to_file.side_effect = Exception(
        "Download failed"
    )

    # Call the function and expect it to raise a RuntimeError
    with pytest.raises(
        RuntimeError, match="Failed to download bundle from GCS: Download failed"
    ):
        execute_bundle_from_gcs(
            bucket=bucket,
            key=key,
            gcp_credentials_block_name="test-credentials",
        )


def test_execute_bundle_from_gcs_execution_failure(
    gcp_credentials: MagicMock,
    mock_bundle_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock the GcpCredentials.load method
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials.load",
        MagicMock(return_value=gcp_credentials),
    )

    # Mock the Runner and its execute_bundle method to raise an exception
    mock_runner = MagicMock(spec=Runner)
    mock_runner.execute_bundle.side_effect = Exception("Execution failed")
    monkeypatch.setattr("prefect.runner.Runner", MagicMock(return_value=mock_runner))

    # Call the function
    bucket = "test-bucket"
    key = "test-key.json"

    def mock_download_to_file(path: str) -> None:
        Path(path).write_bytes(to_json(mock_bundle_data))

    # Set up the mock for download_to_file
    gcp_credentials.get_cloud_storage_client.return_value.bucket.return_value.blob.return_value.download_to_file.side_effect = mock_download_to_file

    # Call the function and expect it to raise a RuntimeError
    with pytest.raises(
        RuntimeError, match="Failed to download bundle from GCS: Execution failed"
    ):
        execute_bundle_from_gcs(
            bucket=bucket,
            key=key,
            gcp_credentials_block_name="test-credentials",
        )
