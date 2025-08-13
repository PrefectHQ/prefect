"""Unit tests for the AWS bundle functionality."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from botocore.exceptions import ClientError
from prefect_aws.experimental.bundles.execute import (
    download_bundle_from_s3,
    execute_bundle_from_s3,
)
from prefect_aws.experimental.bundles.upload import upload_bundle_to_s3


@pytest.fixture(autouse=True)
def mock_start_observer(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("prefect_aws.workers.ecs_worker.start_observer", AsyncMock())
    monkeypatch.setattr("prefect_aws.workers.ecs_worker.stop_observer", AsyncMock())


@pytest.fixture
def mock_s3_client():
    with patch("prefect_aws.credentials.AwsCredentials.get_s3_client") as mock_client:
        s3_client = MagicMock()
        mock_client.return_value = s3_client
        yield s3_client


@pytest.fixture
def mock_bundle_file(tmp_path: Path):
    bundle_path = tmp_path / "test_bundle.json"
    bundle_data = {
        "function": "test_function",
        "context": "test_context",
        "flow_run": {"id": "test_flow_run"},
    }
    bundle_path.write_text(json.dumps(bundle_data))
    return bundle_path


@pytest.fixture
def mock_aws_credentials():
    with (
        patch(
            "prefect_aws.experimental.bundles.upload.AwsCredentials"
        ) as mock_creds_upload,
        patch(
            "prefect_aws.experimental.bundles.execute.AwsCredentials"
        ) as mock_creds_execute,
    ):
        # Create a mock instance with an S3 client
        mock_instance = MagicMock()
        s3_client = MagicMock()
        mock_instance.get_s3_client.return_value = s3_client

        # Configure both mocked classes to return the same instance
        mock_creds_upload.load.return_value = mock_instance
        mock_creds_execute.load.return_value = mock_instance
        mock_creds_upload.return_value = mock_instance
        mock_creds_execute.return_value = mock_instance

        yield mock_instance


@pytest.fixture
def mock_bundle_data():
    """Fixture for consistent bundle data across tests."""
    return {
        "function": "test_function",
        "context": "test_context",
        "flow_run": {"id": "test_flow_run"},
    }


class TestUploadBundle:
    def test_upload_bundle_to_s3_success(
        self, mock_s3_client: MagicMock, mock_bundle_file: Path
    ):
        """Test successful upload of a bundle to S3."""
        result = upload_bundle_to_s3(
            local_filepath=str(mock_bundle_file),
            bucket="test-bucket",
            key="test-key",
        )

        mock_s3_client.upload_file.assert_called_once_with(
            str(mock_bundle_file), "test-bucket", "test-key"
        )
        assert result == {
            "bucket": "test-bucket",
            "key": "test-key",
            "url": "s3://test-bucket/test-key",
        }

    def test_upload_bundle_to_s3_with_credentials(
        self, mock_aws_credentials: MagicMock, mock_bundle_file: Path
    ):
        """Test upload with AWS credentials block name."""
        s3_client = mock_aws_credentials.get_s3_client()

        result = upload_bundle_to_s3(
            local_filepath=str(mock_bundle_file),
            bucket="test-bucket",
            key="test-key",
            aws_credentials_block_name="test-creds",
        )

        s3_client.upload_file.assert_called_once_with(
            str(mock_bundle_file), "test-bucket", "test-key"
        )
        assert result == {
            "bucket": "test-bucket",
            "key": "test-key",
            "url": "s3://test-bucket/test-key",
        }

    def test_upload_bundle_to_s3_default_key(
        self, mock_s3_client: MagicMock, mock_bundle_file: Path
    ):
        """Test upload with default key (using filename)."""
        result = upload_bundle_to_s3(
            local_filepath=str(mock_bundle_file),
            bucket="test-bucket",
            key=None,
        )

        mock_s3_client.upload_file.assert_called_once_with(
            str(mock_bundle_file), "test-bucket", mock_bundle_file.name
        )
        assert result == {
            "bucket": "test-bucket",
            "key": mock_bundle_file.name,
            "url": f"s3://test-bucket/{mock_bundle_file.name}",
        }

    def test_upload_bundle_to_s3_file_not_found(self):
        """Test upload with non-existent file."""
        with pytest.raises(ValueError, match="Bundle file not found"):
            upload_bundle_to_s3(
                local_filepath="nonexistent.json",
                bucket="test-bucket",
                key="test-key",
            )

    def test_upload_bundle_to_s3_client_error(
        self, mock_s3_client: MagicMock, mock_bundle_file: Path
    ):
        """Test upload with S3 client error."""
        mock_s3_client.upload_file.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}}, "upload_file"
        )

        with pytest.raises(RuntimeError, match="Failed to upload bundle to S3"):
            upload_bundle_to_s3(
                local_filepath=str(mock_bundle_file),
                bucket="test-bucket",
                key="test-key",
            )

    @pytest.mark.usefixtures("mock_s3_client")
    def test_upload_bundle_cli(self, mock_bundle_file: Path):
        """Test upload via CLI."""
        from prefect_aws.experimental.bundles import upload

        captured_args: dict[str, Any] = {}
        original_func = upload.upload_bundle_to_s3

        def wrapper(
            local_filepath: str = typer.Argument(...),
            bucket: str = typer.Option(...),
            key: str = typer.Option(...),
            aws_credentials_block_name: Optional[str] = typer.Option(None),
        ):
            captured_args.update(
                {
                    "local_filepath": local_filepath,
                    "bucket": bucket,
                    "key": key,
                    "aws_credentials_block_name": aws_credentials_block_name,
                }
            )
            return original_func(
                local_filepath, bucket, key, aws_credentials_block_name
            )

        upload.upload_bundle_to_s3 = wrapper

        old_argv = sys.argv
        sys.argv = [
            "upload.py",
            str(mock_bundle_file),
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
        ]
        try:
            with patch("sys.exit"):  # Prevent typer from exiting
                upload.typer.run(upload.upload_bundle_to_s3)
        finally:
            sys.argv = old_argv
            upload.upload_bundle_to_s3 = original_func

        assert captured_args == {
            "local_filepath": str(mock_bundle_file),
            "bucket": "test-bucket",
            "key": "test-key",
            "aws_credentials_block_name": None,
        }

    @pytest.mark.usefixtures("mock_s3_client", "mock_aws_credentials")
    def test_upload_bundle_cli_with_credentials(self, mock_bundle_file: Path):
        """Test upload via CLI with AWS credentials."""
        from prefect_aws.experimental.bundles import upload

        captured_args: dict[str, Any] = {}
        original_func = upload.upload_bundle_to_s3

        def wrapper(
            local_filepath: str = typer.Argument(...),
            bucket: str = typer.Option(...),
            key: str = typer.Option(...),
            aws_credentials_block_name: Optional[str] = typer.Option(None),
        ):
            captured_args.update(
                {
                    "local_filepath": local_filepath,
                    "bucket": bucket,
                    "key": key,
                    "aws_credentials_block_name": aws_credentials_block_name,
                }
            )
            return original_func(
                local_filepath, bucket, key, aws_credentials_block_name
            )

        upload.upload_bundle_to_s3 = wrapper

        old_argv = sys.argv
        sys.argv = [
            "upload.py",
            str(mock_bundle_file),
            "--bucket",
            "test-bucket",
            "--key",
            "test-key",
            "--aws-credentials-block-name",
            "test-creds",
        ]
        try:
            with patch("sys.exit"):  # Prevent typer from exiting
                upload.typer.run(upload.upload_bundle_to_s3)
        finally:
            sys.argv = old_argv
            upload.upload_bundle_to_s3 = original_func

        assert captured_args == {
            "local_filepath": str(mock_bundle_file),
            "bucket": "test-bucket",
            "key": "test-key",
            "aws_credentials_block_name": "test-creds",
        }

    @pytest.mark.usefixtures("mock_s3_client")
    def test_upload_bundle_cli_missing_required(self, mock_bundle_file: Path):
        """Test upload via CLI with missing required options."""
        from prefect_aws.experimental.bundles import upload

        # Missing --bucket
        old_argv = sys.argv
        sys.argv = [
            "upload.py",
            str(mock_bundle_file),
            "--key",
            "test-key",
        ]
        try:
            with pytest.raises(SystemExit) as exc_info:
                upload.typer.run(upload.upload_bundle_to_s3)
            assert exc_info.value.code == 2  # Typer exits with code 2 for usage errors
        finally:
            sys.argv = old_argv


class TestDownloadBundle:
    def test_download_bundle_from_s3_success(
        self, mock_s3_client: MagicMock, tmp_path: Path
    ):
        """Test successful download of a bundle from S3."""
        # Create the file that would be downloaded
        test_file = tmp_path / "test-key"
        test_file.write_text("test content")

        def mock_download_file(bucket: str, key: str, filename: str):
            Path(filename).write_text("test content")

        mock_s3_client.download_file.side_effect = mock_download_file

        result = download_bundle_from_s3(
            bucket="test-bucket",
            key="test-key",
            output_dir=str(tmp_path),
        )

        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket", "test-key", str(tmp_path / "test-key")
        )
        assert Path(result["local_path"]).exists()

    def test_download_bundle_from_s3_with_credentials(
        self, mock_aws_credentials: MagicMock, tmp_path: Path
    ):
        """Test download with AWS credentials block name."""
        s3_client = mock_aws_credentials.get_s3_client()

        def mock_download_file(bucket: str, key: str, filename: str):
            Path(filename).write_text("test content")

        s3_client.download_file.side_effect = mock_download_file

        result = download_bundle_from_s3(
            bucket="test-bucket",
            key="test-key",
            output_dir=str(tmp_path),
            aws_credentials_block_name="test-creds",
        )

        s3_client.download_file.assert_called_once()
        assert Path(result["local_path"]).exists()

    def test_download_bundle_from_s3_default_output_dir(
        self, mock_s3_client: MagicMock
    ):
        """Test download with default output directory (temp dir)."""

        def mock_download_file(bucket: str, key: str, filename: str):
            Path(filename).write_text("test content")

        mock_s3_client.download_file.side_effect = mock_download_file

        with patch("tempfile.mkdtemp", return_value="/tmp/test-dir") as mock_mkdtemp:
            result = download_bundle_from_s3(
                bucket="test-bucket",
                key="test-key",
            )

            mock_mkdtemp.assert_called_once_with(prefix="prefect-bundle-")
            mock_s3_client.download_file.assert_called_once()
            assert "local_path" in result

    def test_download_bundle_from_s3_client_error(self, mock_s3_client: MagicMock):
        """Test download with S3 client error."""
        mock_s3_client.download_file.side_effect = ClientError(
            {"Error": {"Code": "TestError", "Message": "Test error"}}, "download_file"
        )

        with pytest.raises(RuntimeError, match="Failed to download bundle from S3"):
            download_bundle_from_s3(
                bucket="test-bucket",
                key="test-key",
            )


class TestExecuteBundle:
    def test_execute_bundle_from_s3(
        self, mock_s3_client: MagicMock, mock_bundle_data: dict[str, Any]
    ):
        """Test execution of a bundle from S3."""

        def mock_download_file(bucket: str, key: str, filename: str):
            Path(filename).write_text(json.dumps(mock_bundle_data))

        mock_s3_client.download_file.side_effect = mock_download_file

        with patch("prefect.runner.Runner.execute_bundle") as mock_execute:
            mock_execute.return_value = None
            execute_bundle_from_s3(
                bucket="test-bucket",
                key="test-key",
            )

            mock_s3_client.download_file.assert_called_once()
            mock_execute.assert_called_once_with(mock_bundle_data)

    def test_execute_bundle_from_s3_with_credentials(
        self, mock_aws_credentials: MagicMock, mock_bundle_data: dict[str, Any]
    ):
        """Test execution with AWS credentials block name."""
        s3_client = mock_aws_credentials.get_s3_client()

        def mock_download_file(bucket: str, key: str, filename: str):
            Path(filename).write_text(json.dumps(mock_bundle_data))

        s3_client.download_file.side_effect = mock_download_file

        with patch("prefect.runner.Runner.execute_bundle") as mock_execute:
            mock_execute.return_value = None
            execute_bundle_from_s3(
                bucket="test-bucket",
                key="test-key",
                aws_credentials_block_name="test-creds",
            )

            s3_client.download_file.assert_called_once()
            mock_execute.assert_called_once_with(mock_bundle_data)

    def test_execute_bundle_invalid_json(self, mock_s3_client: MagicMock):
        """Test execution with invalid JSON bundle data."""

        def mock_download_file(bucket: str, key: str, filename: str):
            Path(filename).write_text("invalid json")

        mock_s3_client.download_file.side_effect = mock_download_file

        with pytest.raises(
            ValueError
        ):  # pydantic_core will raise ValueError for invalid JSON
            execute_bundle_from_s3(
                bucket="test-bucket",
                key="test-key",
            )

    def test_execute_bundle_cli(self, mock_s3_client: MagicMock):
        """Test execution via CLI."""
        with patch("typer.run") as mock_run:
            from prefect_aws.experimental.bundles import execute

            mock_run.assert_not_called()  # Should not be called on import

            old_argv = sys.argv
            sys.argv = ["execute.py", "--bucket", "test-bucket", "--key", "test-key"]
            try:
                execute.typer.run(execute.execute_bundle_from_s3)
            finally:
                sys.argv = old_argv

            mock_run.assert_called_once_with(execute.execute_bundle_from_s3)

    @pytest.mark.usefixtures("mock_s3_client")
    def test_execute_bundle_cli_with_credentials(self):
        """Test execution via CLI with AWS credentials."""
        with patch("typer.run") as mock_run:
            from prefect_aws.experimental.bundles import execute

            old_argv = sys.argv
            sys.argv = [
                "execute.py",
                "--bucket",
                "test-bucket",
                "--key",
                "test-key",
                "--aws-credentials-block-name",
                "test-creds",
            ]
            try:
                execute.typer.run(execute.execute_bundle_from_s3)
            finally:
                sys.argv = old_argv

            mock_run.assert_called_once_with(execute.execute_bundle_from_s3)

    @pytest.mark.usefixtures("mock_s3_client")
    def test_execute_bundle_cli_missing_required(self):
        """Test execution via CLI with missing required options."""
        from prefect_aws.experimental.bundles import execute

        # Missing --key
        old_argv = sys.argv
        sys.argv = [
            "execute.py",
            "--bucket",
            "test-bucket",
        ]
        try:
            with pytest.raises(SystemExit) as exc_info:
                execute.typer.run(execute.execute_bundle_from_s3)
            assert exc_info.value.code == 2  # Typer exits with code 2 for usage errors
        finally:
            sys.argv = old_argv
