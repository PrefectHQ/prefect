import pytest
from unittest.mock import MagicMock

import prefect
from prefect.tasks.google import BigQueryTask, BigQueryStreamingInsertTask
from prefect.utilities.configuration import set_temporary_config


class TestBigQueryInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = BigQueryTask()
        assert task.query is None
        assert task.query_params is None
        assert task.project is None
        assert task.location == "US"
        assert task.dry_run_max_bytes is None
        assert task.credentials_secret == "GOOGLE_APPLICATION_CREDENTIALS"
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
        with pytest.raises(ValueError) as exc:
            task.run()
        assert "query" in str(exc.value)

    @pytest.mark.parametrize("attr", ["dataset_dest", "table_dest"])
    def test_dataset_dest_and_table_dest_are_required_together_eventually(self, attr):
        task = BigQueryTask(**{attr: "some-value"})
        with pytest.raises(ValueError) as exc:
            task.run(query="SELECT *")
        assert attr in str(exc.value)
        assert "must be provided" in str(exc.value)


class TestBigQueryStreamingInsertInitialization:
    def test_initializes_with_nothing_and_sets_defaults(self):
        task = BigQueryStreamingInsertTask()
        assert task.project is None
        assert task.location == "US"
        assert task.credentials_secret == "GOOGLE_APPLICATION_CREDENTIALS"
        assert task.dataset_id is None
        assert task.table is None

    def test_additional_kwargs_passed_upstream(self):
        task = BigQueryStreamingInsertTask(
            name="test-task", checkpoint=True, tags=["bob"]
        )
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize(
        "attr", ["project", "location", "credentials_secret", "dataset_id", "table"]
    )
    def test_initializes_attr_from_kwargs(self, attr):
        task = BigQueryStreamingInsertTask(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    @pytest.mark.parametrize("attr", ["dataset_id", "table"])
    def test_dataset_dest_and_table_dest_are_required_together_eventually(self, attr):
        task = BigQueryStreamingInsertTask(**{attr: "some-value"})
        with pytest.raises(ValueError) as exc:
            task.run(records=[])
        assert attr in str(exc.value)
        assert "must be provided" in str(exc.value)


class TestBigQueryCredentialsandProjects:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = BigQueryTask()

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", creds_loader)
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client", MagicMock()
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={"key": 42})
            ):
                task.run(query="SELECT *")

        assert creds_loader.from_service_account_info.call_args[0][0] == {"key": 42}

    def test_creds_secret_name_can_be_overwritten_at_anytime(self, monkeypatch):
        task = BigQueryTask(credentials_secret="TEST")

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", creds_loader)
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client", MagicMock()
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(TEST=dict(key="42"), RUN=dict())):
                task.run(query="SELECT *")
                task.run(query="SELECT *", credentials_secret="RUN")

        first_call, second_call = creds_loader.from_service_account_info.call_args_list
        assert first_call[0][0] == {"key": "42"}
        assert second_call[0][0] == {}

    def test_project_is_pulled_from_creds_and_can_be_overriden_at_anytime(
        self, monkeypatch
    ):
        task = BigQueryTask()
        task_proj = BigQueryTask(project="test-init")

        client = MagicMock()
        service_account_info = MagicMock(return_value=MagicMock(project_id="default"))
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.Credentials",
            MagicMock(from_service_account_info=service_account_info),
        )
        monkeypatch.setattr("prefect.tasks.google.bigquery.bigquery.Client", client)

        with set_temporary_config({"cloud.use_local_secrets": True}):
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
        task = BigQueryStreamingInsertTask(dataset_id="id", table="table")

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", creds_loader)
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client", MagicMock()
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS=42)):
                task.run(records=[])

        assert creds_loader.from_service_account_info.call_args[0][0] == 42

    def test_creds_secret_name_can_be_overwritten_at_anytime(self, monkeypatch):
        task = BigQueryStreamingInsertTask(
            dataset_id="id", table="table", credentials_secret="TEST"
        )

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.bigquery.Credentials", creds_loader)
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.bigquery.Client", MagicMock()
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(TEST="42", RUN={})):
                task.run(records=[])
                task.run(records=[], credentials_secret="RUN")

        first_call, second_call = creds_loader.from_service_account_info.call_args_list
        assert first_call[0][0] == "42"
        assert second_call[0][0] == {}

    def test_project_is_pulled_from_creds_and_can_be_overriden_at_anytime(
        self, monkeypatch
    ):
        task = BigQueryStreamingInsertTask(dataset_id="id", table="table")
        task_proj = BigQueryStreamingInsertTask(
            dataset_id="id", table="table", project="test-init"
        )

        client = MagicMock()
        service_account_info = MagicMock(return_value=MagicMock(project_id="default"))
        monkeypatch.setattr(
            "prefect.tasks.google.bigquery.Credentials",
            MagicMock(from_service_account_info=service_account_info),
        )
        monkeypatch.setattr("prefect.tasks.google.bigquery.bigquery.Client", client)

        with set_temporary_config({"cloud.use_local_secrets": True}):
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

        with set_temporary_config({"cloud.use_local_secrets": True}):
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

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={})):
                with pytest.raises(ValueError) as exc:
                    task.run(query="SELECT *")

        assert (
            "Query will process 21836427 bytes which is above the set maximum of 1200 for this task"
            in str(exc.value)
        )
