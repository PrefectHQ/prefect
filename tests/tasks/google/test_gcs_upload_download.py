from unittest.mock import MagicMock

import pytest
from google.cloud.exceptions import NotFound

import prefect
from prefect.tasks.google import GCSDownload, GCSUpload
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture(autouse=True, params=["download", "upload"])
def klass(request):
    classes = dict(download=GCSDownload, upload=GCSUpload)
    return classes[request.param]


class TestInitialization:
    def test_initializes_with_bucket_and_sets_defaults(self, klass):
        task = klass(bucket="")
        assert task.bucket == ""
        assert task.blob is None
        assert task.encryption_key_secret is None
        assert task.project is None
        assert task.create_bucket is False

    def test_additional_kwargs_passed_upstream(self, klass):
        task = klass(bucket="", name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    def test_default_bucket_name_is_required(self, klass):
        with pytest.raises(TypeError, match="bucket"):
            task = klass()

    @pytest.mark.parametrize("attr", ["blob", "project"])
    def test_download_initializes_attr_from_kwargs(self, attr):
        task = GCSDownload(bucket="bucket", **{attr: "my-value"})
        assert task.bucket == "bucket"
        assert getattr(task, attr) == "my-value"

    @pytest.mark.parametrize(
        "attr", ["blob", "project", "create_bucket",],
    )
    def test_upload_initializes_attr_from_kwargs(self, attr):
        task = GCSUpload(bucket="bucket", **{attr: "my-value"})
        assert task.bucket == "bucket"
        assert getattr(task, attr) == "my-value"


# Deprecated tests
class TestCredentialsandProjects_DEPRECATED:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch, klass):
        task = klass(bucket="test", credentials_secret="GOOGLE_APPLICATION_CREDENTIALS")
        run_arg = "data" if isinstance(task, GCSUpload) else "blob"

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", creds_loader)
        monkeypatch.setattr("prefect.tasks.google.storage.storage.Client", MagicMock())

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS=42)):
            task.run(**{run_arg: "empty"})

        assert creds_loader.from_service_account_info.call_args[0][0] == 42

    def test_project_is_pulled_from_creds_and_can_be_overriden_at_anytime(
        self, monkeypatch, klass
    ):
        task = klass(bucket="test", credentials_secret="GOOGLE_APPLICATION_CREDENTIALS")
        task_proj = klass(bucket="test", project="test-init")
        run_arg = "data" if isinstance(task, GCSUpload) else "blob"

        client = MagicMock()
        service_account_info = MagicMock(return_value=MagicMock(project_id="default"))
        monkeypatch.setattr(
            "prefect.tasks.google.storage.Credentials",
            MagicMock(from_service_account_info=service_account_info),
        )
        monkeypatch.setattr("prefect.tasks.google.storage.storage.Client", client)

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={})):
            task.run(**{run_arg: "empty"})
            task_proj.run(**{run_arg: "empty"})
            task_proj.run(**{run_arg: "empty", "project": "run-time"})

        x, y, z = client.call_args_list

        assert x[1]["project"] == "default"  ## pulled from credentials
        assert y[1]["project"] == "test-init"  ## pulled from init
        assert z[1]["project"] == "run-time"  ## pulled from run kwarg


class TestBuckets:
    def test_bucket_name_can_be_overwritten_at_runtime(self, monkeypatch, klass):
        task = klass(bucket="test")
        run_arg = "data" if isinstance(task, GCSUpload) else "blob"

        client = MagicMock(get_bucket=MagicMock())
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        task.run(**{run_arg: "empty"}, credentials={})
        task.run(**{run_arg: "empty", "bucket": "run"}, credentials={})

        first, second = client.get_bucket.call_args_list
        assert first[0][0] == "test"
        assert second[0][0] == "run"

    def test_bucket_doesnt_exist_raises_by_default(self, monkeypatch, klass):
        task = klass(bucket="test")
        run_arg = "data" if isinstance(task, GCSUpload) else "blob"

        client = MagicMock(get_bucket=MagicMock(side_effect=NotFound("no bucket")))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        with pytest.raises(NotFound, match="no bucket"):
            task.run(**{run_arg: "empty"}, credentials={})

    def test_bucket_doesnt_exist_can_be_created_on_upload(self, monkeypatch):
        task = GCSUpload(bucket="test", create_bucket=True)

        client = MagicMock(get_bucket=MagicMock(side_effect=NotFound("no bucket")))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        task.run(data="empty", credentials={})
        task.run(data="empty", bucket="run", credentials={})

        assert client.create_bucket.called
        assert client.create_bucket.call_args_list[0][0][0] == "test"
        assert client.create_bucket.call_args_list[1][0][0] == "run"


class TestBlob:
    def test_encryption_key_is_pulled_from_secret_at_runtime(self, monkeypatch, klass):
        task = klass(bucket="test", encryption_key_secret="encrypt",)
        run_arg = "data" if isinstance(task, GCSUpload) else "blob"

        blob = MagicMock()
        client = MagicMock(get_bucket=MagicMock(return_value=MagicMock(blob=blob)))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        with prefect.context(
            secrets=dict(encrypt='"42"', two='"2"', GOOGLE_APPLICATION_CREDENTIALS={})
        ):
            task.run(**{run_arg: "empty"})
            task.run(**{run_arg: "empty", "encryption_key_secret": "two"})

        first, second = blob.call_args_list
        assert first[1]["encryption_key"] == "42"
        assert second[1]["encryption_key"] == "2"

    def test_blob_name_can_be_overwritten_at_runtime_by_upload(self, monkeypatch):
        task = GCSUpload(bucket="test", blob="blobber")

        blob = MagicMock()
        client = MagicMock(get_bucket=MagicMock(return_value=MagicMock(blob=blob)))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        task.run(data="empty", credentials={})
        task.run(data="empty", blob="run-time", credentials={})

        first, second = blob.call_args_list
        assert first[0] == ("blobber",)
        assert second[0] == ("run-time",)

    def test_blob_name_can_be_overwritten_at_runtime_by_download(self, monkeypatch):
        task = GCSDownload(bucket="test", blob="blobber")

        blob = MagicMock()
        client = MagicMock(get_bucket=MagicMock(return_value=MagicMock(blob=blob)))
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", MagicMock())
        monkeypatch.setattr(
            "prefect.tasks.google.storage.storage.Client",
            MagicMock(return_value=client),
        )

        task.run(blob="run-time", credentials={})

        assert blob.call_args[0] == ("run-time",)
