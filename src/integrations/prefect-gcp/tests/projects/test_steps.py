import json
import os
from pathlib import Path, PurePosixPath
from unittest.mock import MagicMock

import pytest
from prefect_gcp.deployments.steps import pull_from_gcs, push_to_gcs

from prefect.utilities.filesystem import relative_path_to_current_platform


@pytest.fixture
def mock_credentials(monkeypatch):
    mock_credentials = MagicMock(name="MockGoogleCredentials")
    mock_authenticated_credentials = MagicMock(token="my-token")
    mock_credentials.from_service_account_info = mock_authenticated_credentials
    mock_credentials.from_service_account_file = mock_authenticated_credentials
    monkeypatch.setattr(
        "prefect_gcp.deployments.steps.Credentials",  # noqa
        mock_credentials,
    )
    mock_auth = MagicMock()
    mock_auth.default.return_value = (mock_authenticated_credentials, "project")
    monkeypatch.setattr(
        "prefect_gcp.deployments.steps.google.auth",  # noqa
        mock_auth,
    )
    return mock_credentials


@pytest.fixture
def gcs_setup(monkeypatch, mock_credentials):
    mocked_storage_client = MagicMock()
    mocked_bucket = MagicMock()
    mocked_blob = MagicMock()

    mocked_storage_client.bucket.return_value = mocked_bucket
    mocked_bucket.blob.return_value = mocked_blob

    monkeypatch.setattr(
        "prefect_gcp.deployments.steps.StorageClient",
        MagicMock(return_value=mocked_storage_client),
    )
    yield mocked_storage_client, mocked_bucket, mocked_blob


@pytest.fixture
def tmp_files(tmp_path: Path):
    files = [
        "testfile1.txt",
        "testfile2.txt",
        "testfile3.txt",
        "testdir1/testfile4.txt",
        "testdir2/testfile5.txt",
    ]

    (tmp_path / ".prefectignore").write_text(
        """
    testdir1/*
    .prefectignore
    """
    )

    for file in files:
        filepath = tmp_path / file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text("Sample text")

    return tmp_path


@pytest.fixture
def dummy_service_account_info():
    info = {
        "type": "service_account",
        "project_id": "dummy_project_id",
        "private_key_id": "dummy_private_key_id",
        "private_key": "dummy_private_key",
        "client_email": "dummy_client_email",
        "client_id": "dummy_client_id",
        "auth_uri": "dummy_auth_uri",
        "token_uri": "dummy_token_uri",
        "auth_provider_x509_cert_url": "dummy_auth_provider_x509_cert_url",
        "client_x509_cert_url": "dummy_client_x509_cert_url",
    }
    return info


@pytest.fixture
def dummy_service_account_file(tmp_path):
    info = {
        "type": "service_account",
        "project_id": "dummy_project_id",
        "private_key_id": "dummy_private_key_id",
        "private_key": "dummy_private_key",
        "client_email": "dummy_client_email",
        "client_id": "dummy_client_id",
        "auth_uri": "dummy_auth_uri",
        "token_uri": "dummy_token_uri",
        "auth_provider_x509_cert_url": "dummy_auth_provider_x509_cert_url",
        "client_x509_cert_url": "dummy_client_x509_cert_url",
    }
    file = tmp_path / "dummy_service_account_file.json"
    file.write_text(json.dumps(info))
    return str(file)


def test_push_to_gcs(gcs_setup, tmp_files, mock_credentials):
    mocked_storage_client, mocked_bucket, mocked_blob = gcs_setup

    bucket_name = "my-test-bucket"
    folder = "my-project"

    os.chdir(tmp_files)

    push_to_gcs(bucket_name, folder)

    # Assert that the StorageClient methods are called with the correct arguments
    mocked_storage_client.bucket.assert_called_with(bucket_name)
    assert mocked_bucket.blob.call_count == 4
    assert mocked_blob.upload_from_filename.call_count == 4
    uploaded_files = [
        args[0][0].name for args in mocked_blob.upload_from_filename.call_args_list
    ]
    assert set(uploaded_files) == {
        "testfile1.txt",
        "testfile2.txt",
        "testfile3.txt",
        "testfile5.txt",
    }


def test_pull_from_gcs(gcs_setup, tmp_path, mock_credentials):
    mocked_storage_client, mocked_bucket, mocked_blob = gcs_setup

    bucket_name = "my-test-bucket"
    folder = "my-project"

    files = {
        f"{folder}/testfile1.txt": "Hello, world!",
        f"{folder}/testfile2.txt": "Test content",
        f"{folder}/testdir1/testfile3.txt": "Nested file",
    }

    class MockBlob:
        def __init__(self, name):
            self.name = name

        def download_to_filename(self, local_blob_download_path):
            for key, content in files.items():
                if local_blob_download_path == PurePosixPath(
                    tmp_path
                    / relative_path_to_current_platform(key).relative_to(folder)
                ):
                    Path(local_blob_download_path).write_text(content)

    # Mock the list_blobs method to return the file names in the GCS bucket
    mocked_storage_client.list_blobs.return_value = [
        MockBlob(name=key) for key in files.keys()
    ]

    os.chdir(tmp_path)
    pull_from_gcs(bucket_name, folder)

    for key, content in files.items():
        target = Path(tmp_path) / PurePosixPath(key).relative_to(folder)
        assert target.exists()
        assert target.read_text() == content


def test_pull_from_gcs_with_service_account_info(
    gcs_setup, tmp_path, dummy_service_account_info, mock_credentials
):
    mocked_storage_client, mocked_bucket, mocked_blob = gcs_setup

    bucket_name = "my-test-bucket"
    folder = "my-project"

    credentials = {
        "service_account_info": dummy_service_account_info,
    }

    os.chdir(tmp_path)
    pull_from_gcs(bucket_name, folder, credentials=credentials)

    mock_credentials.from_service_account_info.assert_called_once_with(
        dummy_service_account_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def test_pull_from_gcs_with_service_account_file(
    gcs_setup, tmp_path, dummy_service_account_file, mock_credentials
):
    mocked_storage_client, mocked_bucket, mocked_blob = gcs_setup

    bucket_name = "my-test-bucket"
    folder = "my-project"

    credentials = {
        "service_account_file": dummy_service_account_file,
    }

    os.chdir(tmp_path)
    pull_from_gcs(bucket_name, folder, credentials=credentials)

    mock_credentials.from_service_account_file.assert_called_once_with(
        dummy_service_account_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def test_push_to_gcs_with_service_account_info(
    gcs_setup, tmp_path, dummy_service_account_info, mock_credentials
):
    mocked_storage_client, mocked_bucket, mocked_blob = gcs_setup

    bucket_name = "my-test-bucket"
    folder = "my-project"

    credentials = {
        "service_account_info": dummy_service_account_info,
    }

    os.chdir(tmp_path)
    push_to_gcs(bucket_name, folder, credentials=credentials)

    mock_credentials.from_service_account_info.assert_called_once_with(
        dummy_service_account_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def test_push_to_gcs_with_service_account_file(
    gcs_setup, tmp_path, dummy_service_account_file, mock_credentials
):
    mocked_storage_client, mocked_bucket, mocked_blob = gcs_setup

    bucket_name = "my-test-bucket"
    folder = "my-project"

    credentials = {
        "service_account_file": dummy_service_account_file,
    }

    os.chdir(tmp_path)
    push_to_gcs(bucket_name, folder, credentials=credentials)

    mock_credentials.from_service_account_file.assert_called_once_with(
        dummy_service_account_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
