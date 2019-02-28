import pytest
from unittest.mock import MagicMock

import prefect
from prefect.tasks.aws import S3DownloadTask, S3UploadTask
from prefect.utilities.configuration import set_temporary_config


class TestS3DownloadTask:
    def test_initialization(self):
        task = S3DownloadTask()
        assert task.aws_credentials_secret == "AWS_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = S3DownloadTask(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_bucket_not_eventually_provided(self):
        task = S3DownloadTask()
        with pytest.raises(ValueError) as exc:
            task.run(key="")
        assert "bucket" in str(exc.value)

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = S3DownloadTask(bucket="bob")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.aws.s3.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS='{"ACCESS_KEY": "42", "SECRET_ACCESS_KEY": "99"}'
                )
            ):
                task.run(key="")
        kwargs = client.call_args[1]
        assert kwargs == {"aws_access_key_id": "42", "aws_secret_access_key": "99"}


class TestS3UploadTask:
    def test_initialization(self):
        task = S3UploadTask()
        assert task.aws_credentials_secret == "AWS_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = S3UploadTask(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_bucket_not_eventually_provided(self):
        task = S3UploadTask()
        with pytest.raises(ValueError) as exc:
            task.run(data="")
        assert "bucket" in str(exc.value)

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = S3UploadTask(bucket="bob")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.tasks.aws.s3.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS='{"ACCESS_KEY": "42", "SECRET_ACCESS_KEY": "99"}'
                )
            ):
                task.run(data="")
        kwargs = client.call_args[1]
        assert kwargs == {"aws_access_key_id": "42", "aws_secret_access_key": "99"}
