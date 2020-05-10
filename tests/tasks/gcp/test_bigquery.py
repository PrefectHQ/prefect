from unittest.mock import MagicMock

import pytest
from google.cloud.exceptions import NotFound

import prefect
from prefect.tasks.gcp import (
    BigQueryLoadGoogleCloudStorage,
    BigQueryLoadFile,
    BigQueryStreamingInsert,
    BigQueryTask,
    CreateBigQueryTable,
)
from prefect.utilities.configuration import set_temporary_config


class TestBigQueryInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = BigQueryTask()
        assert task.query is None
        assert task.query_params is None
        assert task.project is None
        assert task.location == "US"
        assert task.dry_run_max_bytes is None
        assert task.dataset_dest is None
        assert task.table_dest is None
        assert task.job_config == dict()

    def test_additional_kwargs_passed_upstream(self):
        task = BigQueryTask(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize(
        "attr",
        [
            "query",
            "query_params",
            "project",
            "location",
            "dry_run_max_bytes",
            "dataset_dest",
            "table_dest",
            "job_config",
        ],
    )
    def test_initializes_attr_from_kwargs(self, attr):
        task = BigQueryTask(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_query_is_required_eventually(self):
        task = BigQueryTask()
        with pytest.raises(ValueError, match="query"):
            task.run()

    @pytest.mark.parametrize("attr", ["dataset_dest", "table_dest"])
    def test_dataset_dest_and_table_dest_are_required_together_eventually(self, attr):
        task = BigQueryTask(**{attr: "some-value"})
        with pytest.raises(ValueError) as exc:
            task.run(query="SELECT *")
        assert attr in str(exc.value)
        assert "must be provided" in str(exc.value)


class TestBigQueryStreamingInsertInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = BigQueryStreamingInsert()
        assert task.project is None
        assert task.location == "US"
        assert task.dataset_id is None
        assert task.table is None

    def test_additional_kwargs_passed_upstream(self):
        task = BigQueryStreamingInsert(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["project", "location", "dataset_id", "table"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = BigQueryStreamingInsert(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    @pytest.mark.parametrize("attr", ["dataset_id", "table"])
    def test_dataset_dest_and_table_dest_are_required_together_eventually(self, attr):
        task = BigQueryStreamingInsert(**{attr: "some-value"})
        with pytest.raises(ValueError) as exc:
            task.run(records=[])
        assert attr in str(exc.value)
        assert "must be provided" in str(exc.value)


class TestBigQueryLoadGoogleCloudStorageInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = BigQueryLoadGoogleCloudStorage()
        assert task.project is None
        assert task.location == "US"
        assert task.dataset_id is None
        assert task.table is None
        assert task.uri is None

    def test_additional_kwargs_passed_upstream(self):
        task = BigQueryLoadGoogleCloudStorage(
            name="test-task", checkpoint=True, tags=["bob"]
        )
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["project", "location", "dataset_id", "table"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = BigQueryLoadGoogleCloudStorage(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    @pytest.mark.parametrize("attr", ["dataset_id", "table"])
    def test_dataset_dest_and_table_dest_are_required_together_eventually(self, attr):
        task = BigQueryLoadGoogleCloudStorage(**{attr: "some-value"})
        with pytest.raises(ValueError) as exc:
            task.run(uri=None)
        assert attr in str(exc.value)
        assert "must be provided" in str(exc.value)


class TestBigQueryLoadFileInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = BigQueryLoadFile()
        assert task.project is None
        assert task.location == "US"
        assert task.dataset_id is None
        assert task.table is None
        assert task.file is None
        assert task.rewind is False
        assert task.num_retries == 6
        assert task.size is None

    def test_additional_kwargs_passed_upstream(self):
        task = BigQueryLoadFile(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["project", "location", "dataset_id", "table"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = BigQueryLoadFile(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    @pytest.mark.parametrize("attr", ["dataset_id", "table"])
    def test_dataset_dest_and_table_dest_are_required_together_eventually(self, attr):
        task = BigQueryLoadFile(**{attr: "some-value"})
        with pytest.raises(ValueError) as exc:
            task.run(file=None)
        assert attr in str(exc.value)
        assert "must be provided" in str(exc.value)


class TestDryRuns:
    def test_dry_run_doesnt_raise_if_limit_not_exceeded(self, monkeypatch):
        task = BigQueryTask(dry_run_max_bytes=1200)

        client = MagicMock(
            query=MagicMock(return_value=MagicMock(total_bytes_processed=1200))
        )
        monkeypatch.setattr(
            "prefect.tasks.gcp.bigquery.get_bigquery_client",
            MagicMock(return_value=client),
        )

        task.run(query="SELECT *")

    def test_dry_run_raises_if_limit_is_exceeded(self, monkeypatch):
        task = BigQueryTask(dry_run_max_bytes=1200)

        client = MagicMock(
            query=MagicMock(return_value=MagicMock(total_bytes_processed=21836427))
        )
        monkeypatch.setattr(
            "prefect.tasks.gcp.bigquery.get_bigquery_client",
            MagicMock(return_value=client),
        )

        with pytest.raises(
            ValueError,
            match="Query will process 21836427 bytes which is above the set maximum of 1200 for this task",
        ):
            task.run(query="SELECT *")


class TestCreateBigQueryTableInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = CreateBigQueryTable()
        assert task.project is None
        assert task.dataset is None
        assert task.table is None
        assert task.schema is None
        assert task.clustering_fields is None
        assert task.time_partitioning is None

    def test_additional_kwargs_passed_upstream(self):
        task = CreateBigQueryTable(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize(
        "attr",
        [
            "project",
            "dataset",
            "table",
            "schema",
            "clustering_fields",
            "time_partitioning",
        ],
    )
    def test_initializes_attr_from_kwargs(self, attr):
        task = CreateBigQueryTable(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_skip_signal_is_raised_if_table_exists(self, monkeypatch):
        monkeypatch.setattr(
            "prefect.tasks.gcp.bigquery.get_bigquery_client", MagicMock()
        )
        task = CreateBigQueryTable()
        with pytest.raises(prefect.engine.signals.SUCCESS) as exc:
            task.run()

        assert "already exists" in str(exc.value)
