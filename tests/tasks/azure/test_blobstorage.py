from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.azure import BlobStorageDownload, BlobStorageUpload
from prefect.utilities.configuration import set_temporary_config


class TestBlobStorageDownload:
    def test_initialization(self):
        task = BlobStorageDownload()
        assert task.azure_credentials_secret == "AZ_CONNECTION_STRING"

    def test_initialization_passes_to_task_constructor(self):
        task = BlobStorageDownload(name="test", tags=["Azure"])
        assert task.name == "test"
        assert task.tags == {"Azure"}

    def test_raises_if_container_not_eventually_provided(self):
        task = BlobStorageDownload()
        with pytest.raises(ValueError, match="container"):
            task.run(blob_name="")

    def test_connection_string_creds_are_pulled_from_secret_and_runs(self, monkeypatch):
        task = BlobStorageDownload(container="bob")

        client = MagicMock(download_blob=MagicMock())
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        blob = MagicMock(BlockBlobService=MagicMock(service))
        monkeypatch.setattr("prefect.tasks.azure.blobstorage.azure.storage.blob", blob)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CONNECTION_STRING="conn")):
                task.run(blob_name="")


class TestBlobStorageUpload:
    def test_initialization(self):
        task = BlobStorageUpload()
        assert task.azure_credentials_secret == "AZ_CONNECTION_STRING"

    def test_initialization_passes_to_task_constructor(self):
        task = BlobStorageUpload(name="test", tags=["AZ"])
        assert task.name == "test"
        assert task.tags == {"AZ"}

    def test_raises_if_container_not_eventually_provided(self):
        task = BlobStorageUpload()
        with pytest.raises(ValueError, match="container"):
            task.run(data="")

    def test_connection_string_creds_are_pulled_from_secret_and_runs(self, monkeypatch):
        task = BlobStorageUpload(container="bob")

        client = MagicMock(download_blob=MagicMock())
        service = MagicMock(get_blob_client=MagicMock(return_value=client))
        blob = MagicMock(BlockBlobService=MagicMock(service))
        monkeypatch.setattr("prefect.tasks.azure.blobstorage.azure.storage.blob", blob)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CONNECTION_STRING="conn")):
                assert task.run(data="")

    def test_overwrite_passed_to_upload_blob(self, monkeypatch):
        task = BlobStorageUpload(container="bob", overwrite=True)

        data = "blob_data"
        upload_blob = MagicMock()
        blob_client = MagicMock(upload_blob=upload_blob)
        blob_service_client = MagicMock(
            get_blob_client=MagicMock(return_value=blob_client)
        )
        from_connection_string = MagicMock(return_value=blob_service_client)
        blob = MagicMock(
            BlobServiceClient=MagicMock(from_connection_string=from_connection_string)
        )
        monkeypatch.setattr("prefect.tasks.azure.blobstorage.azure.storage.blob", blob)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(AZ_CONNECTION_STRING="conn")):
                assert task.run(data=data)
                upload_blob.assert_called_once_with(data, overwrite=True)
