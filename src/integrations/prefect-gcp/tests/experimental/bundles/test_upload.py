from pathlib import Path
from unittest.mock import MagicMock

import pytest
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.experimental.bundles.upload import upload_bundle_to_gcs


@pytest.fixture
def mock_bundle_file(tmp_path: Path) -> Path:
    bundle_file = tmp_path / "test_bundle.tar.gz"
    bundle_file.write_text("test bundle content")
    return Path(bundle_file)


def test_upload_bundle_to_gcs_success(
    gcp_credentials: GcpCredentials,
    mock_bundle_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials.load",
        MagicMock(return_value=gcp_credentials),
    )
    bucket = "test-bucket"
    key = "test-key.json"

    result = upload_bundle_to_gcs(
        local_filepath=mock_bundle_file,
        bucket=bucket,
        key=key,
        gcp_credentials_block_name="test-credentials",
    )

    assert result == {"bucket": bucket, "key": key}

    # Verify the GCS client was called correctly
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket.assert_called_once_with(bucket)
    gcs_client.bucket(bucket).blob.assert_called_once_with(key)
    gcs_client.bucket(bucket).blob(key).upload_from_file.assert_called_once_with(
        mock_bundle_file
    )


def test_upload_bundle_to_gcs_with_default_key(
    gcp_credentials: GcpCredentials,
    mock_bundle_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials.load",
        MagicMock(return_value=gcp_credentials),
    )
    bucket = "test-bucket"

    result = upload_bundle_to_gcs(
        local_filepath=mock_bundle_file,
        bucket=bucket,
        key="",
        gcp_credentials_block_name="test-credentials",
    )

    assert result == {"bucket": bucket, "key": mock_bundle_file.name}

    # Verify the GCS client was called with the default key
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket(bucket).blob.assert_called_once_with(mock_bundle_file.name)


def test_upload_bundle_to_gcs_with_default_credentials(
    gcp_credentials: GcpCredentials,
    mock_bundle_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials",
        MagicMock(return_value=gcp_credentials),
    )
    bucket = "test-bucket"
    key = "test-key.tar.gz"

    result = upload_bundle_to_gcs(
        local_filepath=mock_bundle_file,
        bucket=bucket,
        key=key,
    )

    assert result == {"bucket": bucket, "key": key}

    # Verify the GCS client was called correctly
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket(bucket).blob(key).upload_from_file.assert_called_once_with(
        mock_bundle_file
    )


def test_upload_bundle_to_gcs_file_not_found(
    gcp_credentials: GcpCredentials, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials.load",
        MagicMock(return_value=gcp_credentials),
    )
    non_existent_file = Path("/non/existent/file.tar.gz")
    bucket = "test-bucket"
    key = "test-key.tar.gz"

    with pytest.raises(ValueError, match=f"Bundle file not found: {non_existent_file}"):
        upload_bundle_to_gcs(
            local_filepath=non_existent_file,
            bucket=bucket,
            key=key,
            gcp_credentials_block_name="test-credentials",
        )


def test_upload_bundle_to_gcs_upload_failure(
    gcp_credentials: GcpCredentials,
    mock_bundle_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "prefect_gcp.credentials.GcpCredentials.load",
        MagicMock(return_value=gcp_credentials),
    )
    bucket = "test-bucket"
    key = "test-key.tar.gz"

    # Mock the upload to raise an exception
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket(bucket).blob(key).upload_from_file.side_effect = Exception(
        "Upload failed"
    )

    with pytest.raises(
        RuntimeError, match="Failed to upload bundle to GCS: Upload failed"
    ):
        upload_bundle_to_gcs(
            local_filepath=mock_bundle_file,
            bucket=bucket,
            key=key,
            gcp_credentials_block_name="test-credentials",
        )
