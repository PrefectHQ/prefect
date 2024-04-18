import os
from pathlib import Path
from unittest.mock import ANY, MagicMock, call

import pytest
from azure.identity import DefaultAzureCredential
from azure.storage.blob import ContainerClient
from prefect_azure.deployments.steps import (
    pull_from_azure_blob_storage,
    push_to_azure_blob_storage,
)


@pytest.fixture
def container_client_mock():
    return MagicMock(spec=ContainerClient)


@pytest.fixture
def default_azure_credential_mock():
    return MagicMock(spec=DefaultAzureCredential)


@pytest.fixture
def mock_azure_blob_storage(
    monkeypatch, container_client_mock, default_azure_credential_mock
):
    monkeypatch.setattr(
        "prefect_azure.deployments.steps.ContainerClient",
        container_client_mock,
    )
    monkeypatch.setattr(
        "prefect_azure.deployments.steps.DefaultAzureCredential",
        default_azure_credential_mock,
    )


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


class TestPush:
    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_push_to_azure_blob_storage_with_connection_string(
        self, tmp_files: Path, container_client_mock: MagicMock
    ):
        container = "test-container"
        folder = "test-folder"
        credentials = {"connection_string": "fake_connection_string"}

        os.chdir(tmp_files)

        push_to_azure_blob_storage(container, folder, credentials)

        container_client_mock.from_connection_string.assert_called_once_with(
            credentials["connection_string"], container_name=container
        )

        upload_blob_mock = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value.upload_blob  # noqa
        )

        upload_blob_mock.assert_has_calls(
            [
                call(
                    f"{folder}/testfile1.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testfile2.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testfile3.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testdir2/testfile5.txt",
                    ANY,
                    overwrite=True,
                ),
            ],
            any_order=True,
        )

        assert all(
            [
                open(call[1][1].name).read() == "Sample text"
                for call in upload_blob_mock.mock_calls
            ]
        )

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_push_to_azure_blob_storage_with_account_url(
        self, tmp_files: Path, container_client_mock: MagicMock
    ):
        container = "test-container"
        folder = "test-folder"
        credentials = {"account_url": "https://fake_account_url.blob.core.windows.net/"}

        os.chdir(tmp_files)

        push_to_azure_blob_storage(container, folder, credentials)

        container_client_mock.assert_called_once_with(
            account_url=credentials["account_url"],
            container_name=container,
            credential=ANY,
        )

        upload_blob_mock = (
            container_client_mock.return_value.__enter__.return_value.upload_blob
        )

        upload_blob_mock.assert_has_calls(
            [
                call(
                    f"{folder}/testfile1.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testfile2.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testfile3.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testdir2/testfile5.txt",
                    ANY,
                    overwrite=True,
                ),
            ],
            any_order=True,
        )

        assert all(
            [
                open(call[1][1].name).read() == "Sample text"
                for call in upload_blob_mock.mock_calls
            ]
        )

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_push_to_azure_blob_storage_missing_credentials(self, tmp_files: Path):
        container = "test-container"
        folder = "test-folder"
        credentials = {}

        os.chdir(tmp_files)

        with pytest.raises(
            ValueError,
            match="Credentials must contain either connection_string or account_url",
        ):
            push_to_azure_blob_storage(container, folder, credentials)

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_push_to_azure_blob_storage_both_credentials_provided(
        self, tmp_files: Path, container_client_mock: MagicMock
    ):
        """connection_string should take precedence over account_url"""
        container = "test-container"
        folder = "test-folder"
        credentials = {
            "account_url": "https://fake_account_url.blob.core.windows.net/",
            "connection_string": "fake_connection_string",
        }

        os.chdir(tmp_files)

        push_to_azure_blob_storage(container, folder, credentials)

        container_client_mock.from_connection_string.assert_called_once_with(
            credentials["connection_string"], container_name=container
        )

        upload_blob_mock = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value.upload_blob  # noqa
        )

        upload_blob_mock.assert_has_calls(
            [
                call(
                    f"{folder}/testfile1.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testfile2.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testfile3.txt",
                    ANY,
                    overwrite=True,
                ),
                call(
                    f"{folder}/testdir2/testfile5.txt",
                    ANY,
                    overwrite=True,
                ),
            ],
            any_order=True,
        )

        assert all(
            [
                open(call[1][1].name).read() == "Sample text"
                for call in upload_blob_mock.mock_calls
            ]
        )

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_push_to_azure_blob_storage_trailing_slash_in_folder(
        self, tmp_files: Path, container_client_mock: MagicMock
    ):
        container = "test-container"
        folder = "test-folder/"
        credentials = {"connection_string": "fake_connection_string"}

        os.chdir(tmp_files)

        push_to_azure_blob_storage(container, folder, credentials)

        upload_blob_mock = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value.upload_blob  # noqa
        )

        # Assert that the trailing slash is properly handled
        upload_blob_mock.assert_has_calls(
            [
                call(
                    "test-folder/testfile1.txt",
                    ANY,
                    overwrite=True,
                ),
                # ... repeat for other files
            ],
            any_order=True,
        )

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_push_to_azure_blob_storage_no_folder_provided(
        self, tmp_files: Path, container_client_mock: MagicMock
    ):
        container = "test-container"
        credentials = {"connection_string": "fake_connection_string"}

        os.chdir(tmp_files)

        push_to_azure_blob_storage(container, "", credentials)

        upload_blob_mock = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value.upload_blob  # noqa
        )

        # Assert that the files are uploaded to the root of the container
        upload_blob_mock.assert_has_calls(
            [
                call(
                    "testfile1.txt",
                    ANY,
                    overwrite=True,
                ),
                # ... repeat for other files
            ],
            any_order=True,
        )


class TestPull:
    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_pull_from_azure_blob_storage_with_connection_string(
        self, tmp_path, container_client_mock
    ):
        container = "test-container"
        folder = "test-folder"
        credentials = {"connection_string": "fake_connection_string"}

        os.chdir(tmp_path)

        blob_mock = MagicMock()
        blob_mock.name = f"{folder}/sample_file.txt"

        mock_context_client = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value  # noqa
        )
        mock_context_client.list_blobs.return_value = [blob_mock]

        pull_from_azure_blob_storage(container, folder, credentials)

        mock_context_client.list_blobs.assert_called_once_with(name_starts_with=folder)
        mock_context_client.download_blob.assert_called_once_with(blob_mock)

        expected_file = tmp_path / "sample_file.txt"
        assert expected_file.exists()

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_pull_from_azure_blob_storage_with_account_url(
        self, tmp_path, container_client_mock
    ):
        container = "test-container"
        folder = "test-folder"
        credentials = {"account_url": "https://fake_account_url.blob.core.windows.net/"}

        os.chdir(tmp_path)

        blob_mock = MagicMock()
        blob_mock.name = f"{folder}/sample_file.txt"

        mock_context_client = container_client_mock.return_value.__enter__.return_value
        mock_context_client.list_blobs.return_value = [blob_mock]

        pull_from_azure_blob_storage(container, folder, credentials)

        container_client_mock.assert_called_once_with(
            account_url=credentials["account_url"],
            container_name=container,
            credential=ANY,
        )

        mock_context_client.list_blobs.assert_called_once_with(name_starts_with=folder)
        mock_context_client.download_blob.assert_called_once_with(blob_mock)

        expected_file = tmp_path / "sample_file.txt"
        assert expected_file.exists()

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_pull_to_azure_blob_storage_missing_credentials(self, tmp_files: Path):
        container = "test-container"
        folder = "test-folder"
        credentials = {}

        os.chdir(tmp_files)

        with pytest.raises(
            ValueError,
            match="Credentials must contain either connection_string or account_url",
        ):
            pull_from_azure_blob_storage(container, folder, credentials)

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_pull_from_azure_blob_storage_both_credentials_provided(
        self, tmp_files: Path, container_client_mock
    ):
        """connection_string should take precedence over account_url"""
        container = "test-container"
        folder = "test-folder"
        credentials = {
            "account_url": "https://fake_account_url.blob.core.windows.net/",
            "connection_string": "fake_connection_string",
        }

        os.chdir(tmp_files)

        blob_mock = MagicMock()
        blob_mock.name = f"{folder}/sample_file.txt"

        mock_context_client = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value  # noqa
        )
        mock_context_client.list_blobs.return_value = [blob_mock]

        pull_from_azure_blob_storage(container, folder, credentials)

        mock_context_client.list_blobs.assert_called_once_with(name_starts_with=folder)
        mock_context_client.download_blob.assert_called_once_with(blob_mock)

        expected_file = tmp_files / "sample_file.txt"
        assert expected_file.exists()

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_pull_from_azure_blob_storage_trailing_slash_in_folder(
        self, tmp_path, container_client_mock
    ):
        container = "test-container"
        folder = "test-folder/"
        credentials = {"connection_string": "fake_connection_string"}

        os.chdir(tmp_path)

        blob_mock = MagicMock()
        blob_mock.name = "test-folder/sample_file.txt"

        mock_context_client = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value  # noqa
        )
        mock_context_client.list_blobs.return_value = [blob_mock]

        pull_from_azure_blob_storage(container, folder, credentials)

        # Assert that the trailing slash is properly handled
        mock_context_client.list_blobs.assert_called_once_with(
            name_starts_with="test-folder/"
        )
        mock_context_client.download_blob.assert_called_once_with(blob_mock)

        expected_file = tmp_path / "sample_file.txt"
        assert expected_file.exists()

    @pytest.mark.usefixtures("mock_azure_blob_storage")
    def test_pull_from_azure_blob_storage_no_folder_provided(
        self, tmp_path, container_client_mock
    ):
        container = "test-container"
        credentials = {"connection_string": "fake_connection_string"}

        os.chdir(tmp_path)

        blob_mock = MagicMock()
        blob_mock.name = "sample_file.txt"

        mock_context_client = (
            container_client_mock.from_connection_string.return_value.__enter__.return_value  # noqa
        )
        mock_context_client.list_blobs.return_value = [blob_mock]

        pull_from_azure_blob_storage(container, "", credentials)

        # Assert that the files are downloaded from the root of the container
        mock_context_client.list_blobs.assert_called_once_with(name_starts_with="")
        mock_context_client.download_blob.assert_called_once_with(blob_mock)

        expected_file = tmp_path / "sample_file.txt"
        assert expected_file.exists()
