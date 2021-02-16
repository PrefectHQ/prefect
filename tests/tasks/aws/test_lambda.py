from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")

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

    def test_lambda_create_exposes_boto3_create_api(self, monkeypatch):
        task = LambdaCreate(
            function_name="test",
            runtime="python3.6",
            role="aws_role",
            handler="file.handler",
        )
        client = MagicMock()
        client.create_function = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        called_method = client.mock_calls[1]
        assert called_method[0] == "().create_function"
        called_method.assert_called_once_with({"FunctionName": "test"})


class TestLambdaDelete:
    def test_initialization(self):
        task = LambdaDelete(function_name="test")

    def test_lambda_delete_exposes_boto3_delete_api(self, monkeypatch):
        task = LambdaDelete(function_name="test")
        client = MagicMock()
        client.delete_function = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        called_method = client.mock_calls[1]
        assert called_method[0] == "().delete_function"
        called_method.assert_called_once_with({"FunctionName": "test"})


class TestLambdaInvoke:
    def test_initialization(self):
        task = LambdaInvoke(function_name="test")

    def test_lambda_invoke_exposes_boto3_invoke_api(self, monkeypatch):
        task = LambdaInvoke(function_name="test")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        called_method = client.mock_calls[1]
        assert called_method[0] == "().invoke"
        called_method.assert_called_once_with({"FunctionName": "test"})


class TestLambdaList:
    def test_initialization(self):
        task = LambdaList()

    def test_lambda_list_exposes_boto3_list_api(self, monkeypatch):
        task = LambdaList()
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        called_method = client.mock_calls[1]
        assert called_method[0] == "().list_functions"
        called_method.assert_called_once_with({"FunctionName": "test"})
