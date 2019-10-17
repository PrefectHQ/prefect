from unittest.mock import MagicMock

import pytest

from prefect.tasks.azureml import (
    DatasetCreateFromDelimitedFiles,
    DatasetCreateFromParquetFiles,
    DatasetCreateFromFiles,
)


@pytest.fixture
def mock_datastore():
    workspace = MagicMock()
    datastore = MagicMock(workspace=workspace)
    return datastore


class TestDatasetCreateFromDelimitedFiles:
    def test_initialization(self):
        name = "my_dataset"
        task = DatasetCreateFromDelimitedFiles(dataset_name=name)

        assert task.dataset_name == name

    def test_missing_name_raises_error(self, mock_datastore):
        name = "my_dataset"

        task = DatasetCreateFromDelimitedFiles(
            dataset_name=name, datastore=mock_datastore
        )

        with pytest.raises(ValueError, match="A path must be provided."):
            task.run()

    def test_tabular_is_called_with_correct_path_object(
        self, mock_datastore, monkeypatch
    ):
        name = "my_dataset"
        path = "foo/bar"
        tabular = MagicMock()
        dataset = MagicMock(Tabular=tabular)
        monkeypatch.setattr(
            "prefect.tasks.azureml.dataset.azureml.core.dataset.Dataset", dataset
        )
        task = DatasetCreateFromDelimitedFiles(
            dataset_name=name, datastore=mock_datastore, path=path
        )

        task.run()

        assert tabular.from_delimited_files.call_args[1]["path"] == [
            (mock_datastore, path)
        ]

    def test_tabular_is_called_with_multiple_correct_path_object(
        self, mock_datastore, monkeypatch
    ):
        name = "my_dataset"
        path = ["/foo/bar", "/my/path"]
        tabular = MagicMock()
        dataset = MagicMock(Tabular=tabular)
        monkeypatch.setattr(
            "prefect.tasks.azureml.dataset.azureml.core.dataset.Dataset", dataset
        )
        task = DatasetCreateFromDelimitedFiles(
            dataset_name=name, datastore=mock_datastore, path=path
        )

        task.run()

        assert tabular.from_delimited_files.call_args[1]["path"] == [
            (mock_datastore, path[0]),
            (mock_datastore, path[1]),
        ]


class TestDatasetCreateFromParquetFiles:
    def test_initialization(self):
        name = "my_dataset"
        task = DatasetCreateFromParquetFiles(dataset_name=name)

        assert task.dataset_name == name

    def test_missing_name_raises_error(self, mock_datastore):
        name = "my_dataset"

        task = DatasetCreateFromParquetFiles(
            dataset_name=name, datastore=mock_datastore
        )

        with pytest.raises(ValueError, match="A path must be provided."):
            task.run()

    def test_tabular_is_called_with_correct_path_object(
        self, mock_datastore, monkeypatch
    ):
        name = "my_dataset"
        path = "foo/bar"
        tabular = MagicMock()
        dataset = MagicMock(Tabular=tabular)
        monkeypatch.setattr(
            "prefect.tasks.azureml.dataset.azureml.core.dataset.Dataset", dataset
        )
        task = DatasetCreateFromParquetFiles(
            dataset_name=name, datastore=mock_datastore, path=path
        )

        task.run()

        assert tabular.from_parquet_files.call_args[1]["path"] == [
            (mock_datastore, path)
        ]

    def test_tabular_is_called_with_multiple_correct_path_object(
        self, mock_datastore, monkeypatch
    ):
        name = "my_dataset"
        path = ["/foo/bar", "/my/path"]
        tabular = MagicMock()
        dataset = MagicMock(Tabular=tabular)
        monkeypatch.setattr(
            "prefect.tasks.azureml.dataset.azureml.core.dataset.Dataset", dataset
        )
        task = DatasetCreateFromParquetFiles(
            dataset_name=name, datastore=mock_datastore, path=path
        )

        task.run()

        assert tabular.from_parquet_files.call_args[1]["path"] == [
            (mock_datastore, path[0]),
            (mock_datastore, path[1]),
        ]


class TestDatasetCreateFromFiles:
    def test_initialization(self):
        name = "my_dataset"
        task = DatasetCreateFromFiles(dataset_name=name)

        assert task.dataset_name == name

    def test_missing_name_raises_error(self, mock_datastore):
        name = "my_dataset"

        task = DatasetCreateFromFiles(dataset_name=name, datastore=mock_datastore)

        with pytest.raises(ValueError, match="A path must be provided."):
            task.run()

    def test_tabular_is_called_with_correct_path_object(
        self, mock_datastore, monkeypatch
    ):
        name = "my_dataset"
        path = "foo/bar"
        file_class = MagicMock()
        dataset = MagicMock(File=file_class)
        monkeypatch.setattr(
            "prefect.tasks.azureml.dataset.azureml.core.dataset.Dataset", dataset
        )
        task = DatasetCreateFromFiles(
            dataset_name=name, datastore=mock_datastore, path=path
        )

        task.run()

        assert file_class.from_files.call_args[1]["path"] == [(mock_datastore, path)]

    def test_tabular_is_called_with_multiple_correct_path_object(
        self, mock_datastore, monkeypatch
    ):
        name = "my_dataset"
        path = ["/foo/bar", "/my/path"]
        file_class = MagicMock()
        dataset = MagicMock(File=file_class)
        monkeypatch.setattr(
            "prefect.tasks.azureml.dataset.azureml.core.dataset.Dataset", dataset
        )
        task = DatasetCreateFromFiles(
            dataset_name=name, datastore=mock_datastore, path=path
        )

        task.run()

        assert file_class.from_files.call_args[1]["path"] == [
            (mock_datastore, path[0]),
            (mock_datastore, path[1]),
        ]
