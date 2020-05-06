from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.aws import S3Download, S3Upload
from prefect.utilities.configuration import set_temporary_config


class TestS3Download:
    def test_initialization(self):
        task = S3Download()

    def test_initialization_passes_to_task_constructor(self):
        task = S3Download(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_bucket_not_eventually_provided(self):
        task = S3Download()
        with pytest.raises(ValueError, match="bucket"):
            task.run(key="")

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = S3Download(bucket="bob")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={"ACCESS_KEY": "42", "SECRET_ACCESS_KEY": "99"}
                )
            ):
                task.run(key="")
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": None,
        }

    def test_creds_default_to_environment(self, monkeypatch):
        task = S3Download(bucket="bob")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run(key="")
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_session_token": None,
        }


class TestS3Upload:
    def test_initialization(self):
        task = S3Upload()

    def test_initialization_passes_to_task_constructor(self):
        task = S3Upload(name="test", tags=["AWS"])
        assert task.name == "test"
        assert task.tags == {"AWS"}

    def test_raises_if_bucket_not_eventually_provided(self):
        task = S3Upload()
        with pytest.raises(ValueError, match="bucket"):
            task.run(data="")

    def test_generated_key_is_str(self, monkeypatch):
        task = S3Upload(bucket="test")
        client = MagicMock()
        boto3 = MagicMock(client=MagicMock(return_value=client))
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={"ACCESS_KEY": "42", "SECRET_ACCESS_KEY": "99"}
                )
            ):
                task.run(data="")
        assert type(client.upload_fileobj.call_args[1]["Key"]) == str

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = S3Upload(bucket="bob")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={"ACCESS_KEY": "42", "SECRET_ACCESS_KEY": "99"}
                )
            ):
                task.run(data="")
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": None,
        }

    def test_creds_default_to_environment(self, monkeypatch):
        task = S3Upload(bucket="bob")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run(data="")
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": None,
            "aws_secret_access_key": None,
            "aws_session_token": None,
        }
