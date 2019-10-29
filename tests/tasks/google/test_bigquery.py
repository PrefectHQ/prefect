from unittest.mock import MagicMock

import pytest
from google.cloud.exceptions import NotFound

import prefect
from prefect.tasks.google import (
    BigQueryLoadGoogleCloudStorage,
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
        assert task.credentials_secret is None
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
            "credentials_secret",
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
        assert task.credentials_secret is None
        assert task.dataset_id is None
        assert task.table is None

    def test_additional_kwargs_passed_upstream(self):
        task = BigQueryStreamingInsert(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize(
        "attr", ["project", "location", "credentials_secret", "dataset_id", "table"]
    )
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
        assert task.credentials_secret is None
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

    @pytest.mark.parametrize(
        "attr", ["project", "location", "credentials_secret", "dataset_id", "table"]
    )
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


class TestBigQueryCredentialsandProjects:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = BigQueryTask(credentials_secret="GOOGLE_APPLICATION_CREDENTIALS")

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", creds_loader)
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client", MagicMock()
        )

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={"key": 42})):
            task.run(query="SELECT *")

        assert creds_loader.from_service_account_info.call_args[0][0] == {"key": 42}

    def test_project_is_pulled_from_creds_and_can_be_overriden_at_anytime(
        self, monkeypatch
    ):
        task = BigQueryTask(credentials_secret="GOOGLE_APPLICATION_CREDENTIALS")
        task_proj = BigQueryTask(
            project="test-init", credentials_secret="GOOGLE_APPLICATION_CREDENTIALS"
        )

        client = MagicMock()
        service_account_info = MagicMock(return_value=MagicMock(project_id="default"))
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.Credentials",
            MagicMock(from_service_account_info=service_account_info),
        )
        monkeypatch.setattr("prefect.tasks.google.bigquery.bigquery.Client", client)

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS=dict())):
            task.run(query="SELECT *")
            task_proj.run(query="SELECT *")
            task_proj.run(query="SELECT *", project="run-time")

        x, y, z = client.call_args_list

        assert x[1]["project"] == "default"  ## pulled from credentials
        assert y[1]["project"] == "test-init"  ## pulled from init
        assert z[1]["project"] == "run-time"  ## pulled from run kwarg


class TestBigQueryStreamingInsertCredentialsandProjects:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = BigQueryStreamingInsert(
            dataset_id="id",
            table="table",
            credentials_secret="GOOGLE_APPLICATION_CREDENTIALS",
        )

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", creds_loader)
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client", MagicMock()
        )

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS=42)):
            task.run(records=[])

        assert creds_loader.from_service_account_info.call_args[0][0] == 42

    def test_project_is_pulled_from_creds_and_can_be_overriden_at_anytime(
        self, monkeypatch
    ):
        task = BigQueryStreamingInsert(
            dataset_id="id",
            table="table",
            credentials_secret="GOOGLE_APPLICATION_CREDENTIALS",
        )
        task_proj = BigQueryStreamingInsert(
            dataset_id="id",
            table="table",
            project="test-init",
            credentials_secret="GOOGLE_APPLICATION_CREDENTIALS",
        )

        client = MagicMock()
        service_account_info = MagicMock(return_value=MagicMock(project_id="default"))
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.Credentials",
            MagicMock(from_service_account_info=service_account_info),
        )
        monkeypatch.setattr("prefect.tasks.google.bigquery.bigquery.Client", client)

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={})):
            task.run(records=[])
            task_proj.run(records=[])
            task_proj.run(records=[], project="run-time")

        x, y, z = client.call_args_list

        assert x[1]["project"] == "default"  ## pulled from credentials
        assert y[1]["project"] == "test-init"  ## pulled from init
        assert z[1]["project"] == "run-time"  ## pulled from run kwarg


class TestDryRuns:
    def test_dry_run_doesnt_raise_if_limit_not_exceeded(self, monkeypatch):
        task = BigQueryTask(dry_run_max_bytes=1200)

        client = MagicMock(
            query=MagicMock(return_value=MagicMock(total_bytes_processed=1200))
        )
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client",
            MagicMock(return_value=client),
        )

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={})):
            task.run(query="SELECT *")

    def test_dry_run_raises_if_limit_is_exceeded(self, monkeypatch):
        task = BigQueryTask(dry_run_max_bytes=1200)

        client = MagicMock(
            query=MagicMock(return_value=MagicMock(total_bytes_processed=21836427))
        )
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client",
            MagicMock(return_value=client),
        )

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={})):
            with pytest.raises(
                ValueError,
                match="Query will process 21836427 bytes which is above the set maximum of 1200 for this task",
            ):
                task.run(query="SELECT *")


class TestCreateBigQueryTableInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = CreateBigQueryTable()
        assert task.project is None
        assert task.credentials_secret is None
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
            "credentials_secret",
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
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client", MagicMock()
        )
        task = CreateBigQueryTable()
        with pytest.raises(prefect.engine.signals.SUCCESS) as exc:
            with prefect.context(
                secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={"key": 42})
            ):
                task.run()

        assert "already exists" in str(exc.value)

    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = CreateBigQueryTable(credentials_secret="GOOGLE_APPLICATION_CREDENTIALS")

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", creds_loader)
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client",
            MagicMock(
                return_value=MagicMock(get_table=MagicMock(side_effect=NotFound("boy")))
            ),
        )

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={"key": 42})):
            task.run()

        assert creds_loader.from_service_account_info.call_args[0][0] == {"key": 42}
