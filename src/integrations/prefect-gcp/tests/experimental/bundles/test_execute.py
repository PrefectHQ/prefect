import zipfile
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

    def mock_download_to_filename(path: str) -> None:
        Path(path).write_bytes(to_json(mock_bundle_data))

    # wow, i love mocking so much
    gcp_credentials.get_cloud_storage_client.return_value.bucket.return_value.blob.return_value.download_to_filename.side_effect = mock_download_to_filename

    execute_bundle_from_gcs(
        bucket=bucket,
        key=key,
        gcp_credentials_block_name="test-credentials",
    )

    # Verify the GCS client was called correctly
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket.assert_called_once_with(bucket)
    gcs_client.bucket(bucket).blob.assert_called_once_with(key)
    gcs_client.bucket(bucket).blob(key).download_to_filename.assert_called_once()

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

    def mock_download_to_filename(path: str) -> None:
        Path(path).write_bytes(to_json(mock_bundle_data))

    # Set up the mock for download_to_filename
    gcp_credentials.get_cloud_storage_client.return_value.bucket.return_value.blob.return_value.download_to_filename.side_effect = mock_download_to_filename

    execute_bundle_from_gcs(
        bucket=bucket,
        key=key,
    )

    # Verify the GCS client was called correctly
    gcs_client = gcp_credentials.get_cloud_storage_client()
    gcs_client.bucket.assert_called_once_with(bucket)
    gcs_client.bucket(bucket).blob.assert_called_once_with(key)
    gcs_client.bucket(bucket).blob(key).download_to_filename.assert_called_once()

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
    gcs_client.bucket(bucket).blob(key).download_to_filename.side_effect = Exception(
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

    def mock_download_to_filename(path: str) -> None:
        Path(path).write_bytes(to_json(mock_bundle_data))

    # Set up the mock for download_to_filename
    gcp_credentials.get_cloud_storage_client.return_value.bucket.return_value.blob.return_value.download_to_filename.side_effect = mock_download_to_filename

    # Call the function and expect it to raise a RuntimeError
    with pytest.raises(
        RuntimeError, match="Failed to download bundle from GCS: Execution failed"
    ):
        execute_bundle_from_gcs(
            bucket=bucket,
            key=key,
            gcp_credentials_block_name="test-credentials",
        )


class TestExecuteBundleFromGCSWithFiles:
    """Tests for GCS bundle execution with included files."""

    def test_execute_with_files_key_downloads_sidecar(
        self,
        gcp_credentials: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When files_key present, sidecar zip is downloaded."""
        bundle_data = {
            "context": "foo",
            "serialize_function": "bar",
            "flow_run": {"name": "buzz", "id": "123"},
            "files_key": "files/abc123.zip",
        }

        monkeypatch.setattr(
            "prefect_gcp.credentials.GcpCredentials.load",
            MagicMock(return_value=gcp_credentials),
        )

        mock_runner = MagicMock(spec=Runner)
        monkeypatch.setattr(
            "prefect.runner.Runner", MagicMock(return_value=mock_runner)
        )

        download_calls: list[str] = []

        def mock_download_to_filename(path: str) -> None:
            download_calls.append(path)
            if path.endswith(".zip"):
                with zipfile.ZipFile(path, "w") as zf:
                    zf.writestr("config.yaml", "key: value")
            else:
                Path(path).write_bytes(to_json(bundle_data))

        gcs_client = gcp_credentials.get_cloud_storage_client()
        gcs_client.bucket.return_value.blob.return_value.download_to_filename.side_effect = mock_download_to_filename

        execute_bundle_from_gcs(
            bucket="test-bucket",
            key="bundle.json",
            gcp_credentials_block_name="test-credentials",
        )

        # Should download both bundle AND sidecar
        assert len(download_calls) == 2

    def test_execute_with_files_extracts_to_cwd(
        self,
        gcp_credentials: MagicMock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Files are extracted to working directory."""
        bundle_data = {
            "context": "foo",
            "serialize_function": "bar",
            "flow_run": {"name": "buzz", "id": "123"},
            "files_key": "files/abc123.zip",
        }

        monkeypatch.setattr(
            "prefect_gcp.credentials.GcpCredentials.load",
            MagicMock(return_value=gcp_credentials),
        )

        mock_runner = MagicMock(spec=Runner)
        monkeypatch.setattr(
            "prefect.runner.Runner", MagicMock(return_value=mock_runner)
        )

        def mock_download_to_filename(path: str) -> None:
            if path.endswith(".zip"):
                with zipfile.ZipFile(path, "w") as zf:
                    zf.writestr("data/config.yaml", "key: value")
            else:
                Path(path).write_bytes(to_json(bundle_data))

        gcs_client = gcp_credentials.get_cloud_storage_client()
        gcs_client.bucket.return_value.blob.return_value.download_to_filename.side_effect = mock_download_to_filename

        monkeypatch.chdir(tmp_path)

        execute_bundle_from_gcs(
            bucket="test-bucket",
            key="bundle.json",
            gcp_credentials_block_name="test-credentials",
        )

        # File should be extracted to cwd
        extracted_file = tmp_path / "data" / "config.yaml"
        assert extracted_file.exists()
        assert extracted_file.read_text() == "key: value"

    def test_execute_without_files_key_unchanged(
        self,
        gcp_credentials: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Execution without files_key works as before."""
        bundle_data = {
            "context": "foo",
            "serialize_function": "bar",
            "flow_run": {"name": "buzz", "id": "123"},
        }

        monkeypatch.setattr(
            "prefect_gcp.credentials.GcpCredentials.load",
            MagicMock(return_value=gcp_credentials),
        )

        mock_runner = MagicMock(spec=Runner)
        monkeypatch.setattr(
            "prefect.runner.Runner", MagicMock(return_value=mock_runner)
        )

        download_calls: list[str] = []

        def mock_download_to_filename(path: str) -> None:
            download_calls.append(path)
            Path(path).write_bytes(to_json(bundle_data))

        gcs_client = gcp_credentials.get_cloud_storage_client()
        gcs_client.bucket.return_value.blob.return_value.download_to_filename.side_effect = mock_download_to_filename

        execute_bundle_from_gcs(
            bucket="test-bucket",
            key="bundle.json",
            gcp_credentials_block_name="test-credentials",
        )

        # Should only download bundle
        assert len(download_calls) == 1

    def test_execute_with_files_key_none_no_extraction(
        self,
        gcp_credentials: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No extraction when files_key is explicitly None."""
        bundle_data = {
            "context": "foo",
            "serialize_function": "bar",
            "flow_run": {"name": "buzz", "id": "123"},
            "files_key": None,
        }

        monkeypatch.setattr(
            "prefect_gcp.credentials.GcpCredentials.load",
            MagicMock(return_value=gcp_credentials),
        )

        mock_runner = MagicMock(spec=Runner)
        monkeypatch.setattr(
            "prefect.runner.Runner", MagicMock(return_value=mock_runner)
        )

        download_calls: list[str] = []

        def mock_download_to_filename(path: str) -> None:
            download_calls.append(path)
            Path(path).write_bytes(to_json(bundle_data))

        gcs_client = gcp_credentials.get_cloud_storage_client()
        gcs_client.bucket.return_value.blob.return_value.download_to_filename.side_effect = mock_download_to_filename

        execute_bundle_from_gcs(
            bucket="test-bucket",
            key="bundle.json",
            gcp_credentials_block_name="test-credentials",
        )

        # Should only download bundle
        assert len(download_calls) == 1
