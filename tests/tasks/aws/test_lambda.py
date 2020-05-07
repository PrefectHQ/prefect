from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.aws import LambdaCreate, LambdaDelete, LambdaInvoke, LambdaList
from prefect.utilities.configuration import set_temporary_config


class TestLambdaCreate:
    def test_initialization(self):
        task = LambdaCreate(
            function_name="test",
            runtime="python3.6",
            role="aws_role",
            handler="file.handler",
            bucket="s3_bucket",
            bucket_key="bucket_key",
        )
        assert task.code == {"S3Bucket": "s3_bucket", "S3Key": "bucket_key"}

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = LambdaCreate(
            function_name="test",
            runtime="python3.6",
            role="aws_role",
            handler="file.handler",
            bucket="s3_bucket",
            bucket_key="bucket_key",
        )
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={
                        "ACCESS_KEY": "42",
                        "SECRET_ACCESS_KEY": "99",
                        "SESSION_TOKEN": "1",
                    }
                )
            ):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }

    def test_credentials_are_used_when_passed_at_runtime(self, monkeypatch):
        task = LambdaCreate(
            function_name="test",
            runtime="python3.6",
            role="aws_role",
            handler="file.handler",
            bucket="s3_bucket",
            bucket_key="bucket_key",
        )
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        credentials = {
            "ACCESS_KEY": "42",
            "SECRET_ACCESS_KEY": "99",
            "SESSION_TOKEN": "1",
        }

        task.run(credentials=credentials)
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }


class TestLambdaDelete:
    def test_initialization(self):
        task = LambdaDelete(function_name="test")

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = LambdaDelete(function_name="test")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={
                        "ACCESS_KEY": "42",
                        "SECRET_ACCESS_KEY": "99",
                        "SESSION_TOKEN": "1",
                    }
                )
            ):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }

    def test_credentials_are_used_when_passed_at_runtime(self, monkeypatch):
        task = LambdaDelete(function_name="test")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        credentials = {
            "ACCESS_KEY": "42",
            "SECRET_ACCESS_KEY": "99",
            "SESSION_TOKEN": "1",
        }

        task.run(credentials=credentials)
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }


class TestLambdaInvoke:
    def test_initialization(self):
        task = LambdaInvoke(function_name="test")

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = LambdaInvoke(function_name="test")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={
                        "ACCESS_KEY": "42",
                        "SECRET_ACCESS_KEY": "99",
                        "SESSION_TOKEN": "1",
                    }
                )
            ):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }

    def test_credentials_are_used_when_passed_at_runtime(self, monkeypatch):
        task = LambdaInvoke(function_name="test")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        credentials = {
            "ACCESS_KEY": "42",
            "SECRET_ACCESS_KEY": "99",
            "SESSION_TOKEN": "1",
        }

        task.run(credentials=credentials)
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }


class TestLambdaList:
    def test_initialization(self):
        task = LambdaList()

    def test_creds_are_pulled_from_secret(self, monkeypatch):
        task = LambdaList()
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(
                    AWS_CREDENTIALS={
                        "ACCESS_KEY": "42",
                        "SECRET_ACCESS_KEY": "99",
                        "SESSION_TOKEN": "1",
                    }
                )
            ):
                task.run()
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }

    def test_credentials_are_used_when_passed_at_runtime(self, monkeypatch):
        task = LambdaList()
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        credentials = {
            "ACCESS_KEY": "42",
            "SECRET_ACCESS_KEY": "99",
            "SESSION_TOKEN": "1",
        }

        task.run(credentials=credentials)
        kwargs = client.call_args[1]
        assert kwargs == {
            "aws_access_key_id": "42",
            "aws_secret_access_key": "99",
            "aws_session_token": "1",
        }
