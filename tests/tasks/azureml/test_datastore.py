import os
from unittest.mock import MagicMock

import pytest

from azureml.core.workspace import Workspace

import prefect
from prefect.tasks.azureml import (
    DatastoreRegisterBlobContainer,
    DatastoreList,
    DatastoreGet,
    DatastoreUpload,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def mock_workspace():
    return MagicMock(spec=Workspace)


class TestDatastoreRegisterBlobContainer:
    def test_initialization(self, mock_workspace):
        container_name = "my_container"
        task = DatastoreRegisterBlobContainer(
            workspace=mock_workspace, container_name=container_name
        )

        assert task.workspace == mock_workspace
        assert task.container_name == container_name

    def test_missing_container_name_raises_error(self, mock_workspace):
        task = DatastoreRegisterBlobContainer(workspace=mock_workspace)

        with pytest.raises(ValueError, match="A container name must be provided."):
            task.run()

    def test_datastore_name_used_in_register_call(self, mock_workspace, monkeypatch):
        container_name = "my_container"
        datastore_name = "foobar"
        task = DatastoreRegisterBlobContainer(workspace=mock_workspace)

        datastore_class = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.azureml.datastore.azureml.core.datastore.Datastore",
            datastore_class,
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS={"ACCOUNT_NAME": "42", "ACCOUNT_KEY": "99"})
            ):
                task.run(container_name=container_name, datastore_name=datastore_name)

        assert (
            datastore_class.register_azure_blob_container.call_args[1]["datastore_name"]
            == datastore_name
        )

    def test_container_name_used_in_register_call(self, mock_workspace, monkeypatch):
        container_name = "my_container"
        task = DatastoreRegisterBlobContainer(workspace=mock_workspace)

        datastore_class = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.azureml.datastore.azureml.core.datastore.Datastore",
            datastore_class,
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS={"ACCOUNT_NAME": "42", "ACCOUNT_KEY": "99"})
            ):
                task.run(container_name=container_name)

        assert (
            datastore_class.register_azure_blob_container.call_args[1]["datastore_name"]
            == container_name
        )

    def test_register_call_uses_account_key(self, mock_workspace, monkeypatch):
        container_name = "my_container"
        task = DatastoreRegisterBlobContainer(workspace=mock_workspace)

        datastore_class = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.azureml.datastore.azureml.core.datastore.Datastore",
            datastore_class,
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS={"ACCOUNT_NAME": "42", "ACCOUNT_KEY": "99"})
            ):
                task.run(container_name=container_name)

        assert (
            datastore_class.register_azure_blob_container.call_args[1]["account_key"]
            == "99"
        )

    def test_register_call_uses_sas_token(self, mock_workspace, monkeypatch):
        container_name = "my_container"
        task = DatastoreRegisterBlobContainer(workspace=mock_workspace)

        datastore_class = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.azureml.datastore.azureml.core.datastore.Datastore",
            datastore_class,
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS={"ACCOUNT_NAME": "42", "SAS_TOKEN": "24"})
            ):
                task.run(container_name=container_name)

        assert (
            datastore_class.register_azure_blob_container.call_args[1]["sas_token"]
            == "24"
        )


class TestDatastoreList:
    def test_initialization(self, mock_workspace):
        task = DatastoreList(workspace=mock_workspace)

        assert task.workspace == mock_workspace

    def test_return_datastore_dict(self, mock_workspace):
        datastores_dict = {"my_datast": MagicMock()}
        mock_workspace.datastores = datastores_dict

        task = DatastoreList(workspace=mock_workspace)

        output_dict = task.run()

        assert output_dict == datastores_dict


class TestDatastoreGet:
    def test_initialization(self, mock_workspace):
        task = DatastoreGet(workspace=mock_workspace)

        assert task.workspace == mock_workspace

    def test_get_called_with_defined_datastore_name(self, mock_workspace, monkeypatch):
        datastore_class = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.azureml.datastore.azureml.core.datastore.Datastore",
            datastore_class,
        )

        task = DatastoreGet(workspace=mock_workspace, datastore_name="my_datastore")

        task.run()

        assert datastore_class.get

    def test_get_default_called_without_defined_datastore_name(
        self, mock_workspace, monkeypatch
    ):
        datastore_class = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.azureml.datastore.azureml.core.datastore.Datastore",
            datastore_class,
        )

        task = DatastoreGet(workspace=mock_workspace)

        task.run()

        assert datastore_class.get_default


class TestDatastoreUpload:
    def test_initialization(self):
        relative_root = "/foo/bar"
        task = DatastoreUpload(relative_root=relative_root)

        assert task.relative_root == relative_root

    def test_missing_datastore_path_raises_error(self):
        path = ""
        task = DatastoreUpload(path=path)

        with pytest.raises(ValueError, match="A datastore must be provided."):
            task.run()

    def test_missing_datastore_datastore_raises_error(self):
        datastore = MagicMock()
        task = DatastoreUpload(datastore=datastore)

        with pytest.raises(ValueError, match="A path must be provided."):
            task.run()

    def test_upload_files_called_with_single_file(self):
        datastore = MagicMock()
        path = "foo/bar"
        assert not os.path.isdir(path)
        task = DatastoreUpload(datastore=datastore, path=path)

        task.run()

        assert datastore.upload_files.call_args[1]["files"] == [path]

    def test_upload_files_called_with_multiple_files(self):
        datastore = MagicMock()
        path = ["foo/bar", "my/path"]

        assert not any([os.path.isdir(path_item) for path_item in path])
        task = DatastoreUpload(datastore=datastore, path=path)

        task.run()

        assert datastore.upload_files.call_args[1]["files"] == path

    def test_upload_called_with_directory(self, monkeypatch):
        mocked_isdir = MagicMock()
        mocked_isdir.return_value = True
        monkeypatch.setattr("os.path.isdir", mocked_isdir)

        datastore = MagicMock()
        path = "foo/bar"

        task = DatastoreUpload(datastore=datastore, path=path)

        task.run()

        assert datastore.upload.call_args[1]["src_dir"] == path


# test with folder
