from unittest.mock import MagicMock

import pytest
from google.cloud.exceptions import NotFound

import prefect
import prefect.utilities.gcp
from prefect.tasks.gcp import GCSDownload, GCSUpload
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

    @pytest.mark.parametrize("attr", ["blob", "project", "create_bucket"])
    def test_upload_initializes_attr_from_kwargs(self, attr):
        task = GCSUpload(bucket="bucket", **{attr: "my-value"})
        assert task.bucket == "bucket"
        assert getattr(task, attr) == "my-value"


class TestBuckets:
    def test_bucket_name_can_be_overwritten_at_runtime(self, monkeypatch, klass):
        task = klass(bucket="test")
        run_arg = "data" if isinstance(task, GCSUpload) else "blob"

        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.gcp.storage.get_storage_client", client)

        task.run(**{run_arg: "empty"}, credentials={})
        task.run(**{run_arg: "empty", "bucket": "run"}, credentials={})

        first, second = client.return_value.get_bucket.call_args_list
        assert first[0][0] == "test"
        assert second[0][0] == "run"

    def test_bucket_doesnt_exist_raises_by_default(self, monkeypatch, klass):
        task = klass(bucket="test")
        run_arg = "data" if isinstance(task, GCSUpload) else "blob"

        client = MagicMock()
        client.return_value = MagicMock(
            get_bucket=MagicMock(side_effect=NotFound("no bucket"))
        )
        monkeypatch.setattr("prefect.tasks.gcp.storage.get_storage_client", client)

        with pytest.raises(NotFound, match="no bucket"):
            task.run(**{run_arg: "empty"}, credentials={})

    def test_bucket_doesnt_exist_can_be_created_on_upload(self, monkeypatch):
        task = GCSUpload(bucket="test", create_bucket=True)

        client = MagicMock()
        client.return_value = MagicMock(
            get_bucket=MagicMock(side_effect=NotFound("no bucket"))
        )
        monkeypatch.setattr("prefect.tasks.gcp.storage.get_storage_client", client)

        task.run(data="empty", credentials={})
        task.run(data="empty", bucket="run", credentials={})

        assert client.return_value.create_bucket.called
        assert client.return_value.create_bucket.call_args_list[0][0][0] == "test"
        assert client.return_value.create_bucket.call_args_list[1][0][0] == "run"


class TestBlob:
    def test_blob_name_can_be_overwritten_at_runtime_by_upload(self, monkeypatch):
        task = GCSUpload(bucket="test", blob="blobber")

        blob = MagicMock()
        client = MagicMock()
        client.return_value = MagicMock(
            get_bucket=MagicMock(return_value=MagicMock(blob=blob))
        )
        monkeypatch.setattr("prefect.tasks.gcp.storage.get_storage_client", client)

        task.run(data="empty", credentials={})
        task.run(data="empty", blob="run-time", credentials={})

        first, second = blob.call_args_list
        assert first[0] == ("blobber",)
        assert second[0] == ("run-time",)

    def test_blob_name_can_be_overwritten_at_runtime_by_download(self, monkeypatch):
        task = GCSDownload(bucket="test", blob="blobber")

        blob = MagicMock()
        client = MagicMock()
        client.return_value = MagicMock(
            get_bucket=MagicMock(return_value=MagicMock(blob=blob))
        )
        monkeypatch.setattr("prefect.tasks.gcp.storage.get_storage_client", client)

        task.run(blob="run-time", credentials={})

        assert blob.call_args[0] == ("run-time",)
