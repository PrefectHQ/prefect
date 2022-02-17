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
            runtime="python3.7",
            role="aws_role",
            handler="file.handler",
            bucket="s3_bucket",
            bucket_key="bucket_key",
        )
        assert task.code == {"S3Bucket": "s3_bucket", "S3Key": "bucket_key"}

    def test_lambda_create_exposes_boto3_create_api(self, monkeypatch):
        task = LambdaCreate(
            function_name="test",
            runtime="python3.7",
            role="aws_role",
            handler="file.handler",
        )
        client = MagicMock()
        client.create_function = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        client().create_function.assert_called_once_with(
            FunctionName="test",
            Runtime="python3.7",
            Role="aws_role",
            Handler="file.handler",
            Code={"S3Bucket": "", "S3Key": ""},
            Description="",
            Timeout=3,
            MemorySize=128,
            Publish=True,
            VpcConfig={},
            DeadLetterConfig={},
            Environment={"Variables": {}},
            KMSKeyArn="",
            TracingConfig={"Mode": "PassThrough"},
            Tags={},
            Layers=[],
        )


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

        client().delete_function.assert_called_once_with(FunctionName="test")


class TestLambdaInvoke:
    def test_initialization(self):
        task = LambdaInvoke(function_name="test")

    def test_lambda_invoke_exposes_boto3_invoke_api(self, monkeypatch):
        task = LambdaInvoke(function_name="test")
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        client().invoke.assert_called_once_with(
            FunctionName="test",
            InvocationType="RequestResponse",
            LogType="None",
            ClientContext="eyJjdXN0b20iOiBudWxsLCAiZW52IjogbnVsbCwgImNsaWVudCI6IG51bGx9",
            Payload="null",
            Qualifier="$LATEST",
        )


class TestLambdaList:
    def test_initialization(self):
        task = LambdaList()

    def test_lambda_list_exposes_boto3_list_api(self, monkeypatch):
        task = LambdaList()
        client = MagicMock()
        boto3 = MagicMock(client=client)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
        task.run()

        client().list_functions.assert_called_once_with(
            MasterRegion="ALL",
            FunctionVersion="ALL",
            MaxItems=50,
        )
