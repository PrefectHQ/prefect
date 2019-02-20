import pytest
from google.cloud.exceptions import NotFound
from unittest.mock import MagicMock

import prefect
from prefect.tasks.google import GoogleCloudStorageTask
from prefect.utilities.configuration import set_temporary_config


class TestInitialization:
    def test_initializes_with_bucket_and_sets_defaults(self):
        task = GoogleCloudStorageTask(bucket="")
        assert task.bucket == ""
        assert task.blob is None
        assert task.encryption_key_secret is None
        assert task.credentials_secret == "GOOGLE_APPLICATION_CREDENTIALS"
        assert task.project is None
        assert task.create_bucket is False

    def test_additional_kwargs_passed_upstream(self):
        task = GoogleCloudStorageTask(bucket="", name="test-task")
        assert task.name == "test-task"

    def test_default_bucket_name_is_required(self):
        with pytest.raises(TypeError) as exc:
            task = GoogleCloudStorageTask()

        assert "bucket" in str(exc.value)

    @pytest.mark.parametrize(
        "attr",
        [
            "blob",
            "encryption_key_secret",
            "credentials_secret",
            "project",
            "create_bucket",
        ],
    )
    def test_initializes_attr_from_kwargs(self, attr):
        task = GoogleCloudStorageTask(bucket="bucket", **{attr: "my-value"})
        assert task.bucket == "bucket"
        assert getattr(task, attr) == "my-value"


class TestCredentialsandProjects:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = GoogleCloudStorageTask(bucket="test")

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", creds_loader)
        monkeypatch.setattr("prefect.tasks.google.storage.storage.Client", MagicMock())

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS="42")):
                task.run(data="empty")

        assert creds_loader.from_service_account_info.call_args[0][0] == 42

    def test_creds_secret_name_can_be_overwritten_at_anytime(self, monkeypatch):
        task = GoogleCloudStorageTask(bucket="test", credentials_secret="TEST")

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", creds_loader)
        monkeypatch.setattr("prefect.tasks.google.storage.storage.Client", MagicMock())

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(TEST="42", RUN="{}")):
                task.run(data="empty")
                task.run(data="empty", credentials_secret="RUN")

        first_call, second_call = creds_loader.from_service_account_info.call_args_list
        assert first_call[0][0] == 42
        assert second_call[0][0] == {}

    def test_project_is_pulled_from_creds_and_can_be_overriden_at_anytime(
        self, monkeypatch
    ):
        task = GoogleCloudStorageTask(bucket="test")
        task_proj = GoogleCloudStorageTask(bucket="test", project="test-init")

        client = MagicMock()
        service_account_info = MagicMock(return_value=MagicMock(project_id="default"))
        monkeypatch.setattr(
            "prefect.tasks.google.storage.Credentials",
            MagicMock(from_service_account_info=service_account_info),
        )
        monkeypatch.setattr("prefect.tasks.google.storage.storage.Client", client)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS="{}")):
                task.run(data="empty")
                task_proj.run(data="empty")
                task_proj.run(data="empty", project="run-time")

        x, y, z = client.call_args_list

        assert x[1]["project"] == "default"  ## pulled from credentials
        assert y[1]["project"] == "test-init"  ## pulled from init
        assert z[1]["project"] == "run-time"  ## pulled from run kwarg


class TestBuckets:
    def test_bucket_name_can_be_overwritten_at_runtime(self, monkeypatch):
        task = GoogleCloudStorageTask(bucket="test")

        client = MagicMock(get_bucket=MagicMock())
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS="{}")):
                task.run(data="empty")
                task.run(data="empty", bucket="run")

        first, second = client.get_bucket.call_args_list
        assert first[0][0] == "test"
        assert second[0][0] == "run"

    def test_bucket_doesnt_exist_raises_by_default(self, monkeypatch):
        task = GoogleCloudStorageTask(bucket="test")

        client = MagicMock(get_bucket=MagicMock(side_effect=NotFound("no bucket")))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS="{}")):
                with pytest.raises(NotFound) as exc:
                    task.run(data="empty")

        assert "no bucket" in str(exc.value)

    def test_bucket_doesnt_exist_can_be_created(self, monkeypatch):
        task = GoogleCloudStorageTask(bucket="test", create_bucket=True)

        client = MagicMock(get_bucket=MagicMock(side_effect=NotFound("no bucket")))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS="{}")):
                task.run(data="empty")
                task.run(data="empty", bucket="run")

        assert client.create_bucket.called
        assert client.create_bucket.call_args_list[0][0][0] == "test"
        assert client.create_bucket.call_args_list[1][0][0] == "run"


class TestBlob:
    def test_encryption_key_is_pulled_from_secret_at_runtime(self, monkeypatch):
        task = GoogleCloudStorageTask(bucket="test", encryption_key_secret="encrypt")

        blob = MagicMock()
        client = MagicMock(get_bucket=MagicMock(return_value=MagicMock(blob=blob)))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(encrypt="42", GOOGLE_APPLICATION_CREDENTIALS="{}")
            ):
                task.run(data="empty")

        assert blob.call_args[1]["encryption_key"] == "42"
        assert blob.call_args[0][0].startswith("prefect")

    def test_blob_name_can_be_overwritten_at_runtime(self, monkeypatch):
        task = GoogleCloudStorageTask(bucket="test", blob="blobber")

        blob = MagicMock()
        client = MagicMock(get_bucket=MagicMock(return_value=MagicMock(blob=blob)))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(encrypt="42", GOOGLE_APPLICATION_CREDENTIALS="{}")
            ):
                task.run(data="empty")
                task.run(data="empty", blob="run-time")

        first, second = blob.call_args_list
        assert first[0] == ("blobber",)
        assert second[0] == ("run-time",)
