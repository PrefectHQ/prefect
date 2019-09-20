from unittest.mock import MagicMock
from prefect.tasks.azure.blobstorage import BlobStorageUpload
from prefect.tasks.azure.blobstorage import BlobStorageUpload

import pytest

import azure.storage.blob

import prefect
from prefect.tasks.azure import BlobStorageDownload, BlobStorageUpload
from prefect.utilities.configuration import set_temporary_config


class TestBlobStorageDownload:
    def test_initialization(self):
        task = BlobStorageDownload()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = BlobStorageDownload(name="test", tags=["Azure"])
        assert task.name == "test"
        assert task.tags == {"Azure"}

    def test_raises_if_container_not_eventually_provided(self):
        task = BlobStorageDownload()
        with pytest.raises(ValueError, match="container"):
            task.run(blob_name="")

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = BlobStorageDownload(container="bob")
        service = MagicMock()
        blob = MagicMock(BlockBlobService=service)
        monkeypatch.setattr("prefect.tasks.azure.blobstorage.azure.storage.blob", blob)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS={"ACCOUNT_NAME": "42", "ACCOUNT_KEY": "99"})
            ):
                task.run(blob_name="")
        kwargs = service.call_args[1]
        assert kwargs == {"account_name": "42", "account_key": "99"}


class TestBlobStorageUpload:
    def test_initialization(self):
        task = BlobStorageUpload()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = BlobStorageUpload(name="test", tags=["AZ"])
        assert task.name == "test"
        assert task.tags == {"AZ"}

    def test_raises_if_container_not_eventually_provided(self):
        task = BlobStorageUpload()
        with pytest.raises(ValueError, match="container"):
            task.run(data="")

    def test_generated_key_is_str(self, monkeypatch):
        task = BlobStorageUpload(container="test")
        service = MagicMock()
        blob = MagicMock(BlockBlobService=MagicMock(return_value=service))
        monkeypatch.setattr("prefect.tasks.azure.blobstorage.azure.storage.blob", blob)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS={"ACCOUNT_NAME": "42", "ACCOUNT_KEY": "99"})
            ):
                task.run(data="")
        assert type(service.create_blob_from_text.call_args[1]["blob_name"]) == str

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = BlobStorageUpload(container="bob")
        service = MagicMock()
        blob = MagicMock(BlockBlobService=service)
        monkeypatch.setattr("prefect.tasks.azure.blobstorage.azure.storage.blob", blob)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS={"ACCOUNT_NAME": "42", "ACCOUNT_KEY": "99"})
            ):
                task.run(data="")
        kwargs = service.call_args[1]
        assert kwargs == {"account_name": "42", "account_key": "99"}
