from unittest.mock import MagicMock

import cloudpickle
import pytest

import prefect
from prefect.engine.results import S3Result
from prefect.utilities.configuration import set_temporary_config

pytest.importorskip("boto3")
pytest.importorskip("botocore")


@pytest.fixture
def mock_boto3(monkeypatch):
    from prefect.utilities.aws import _CLIENT_CACHE

    _CLIENT_CACHE.clear()

    boto3 = MagicMock()
    monkeypatch.setattr("prefect.utilities.aws.boto3", boto3)
    secrets = dict(
        AWS_CREDENTIALS=dict(
            ACCESS_KEY="access_key", SECRET_ACCESS_KEY="secret_access_key"
        )
    )
    with set_temporary_config({"cloud.use_local_secrets": True}), prefect.context(
        secrets=secrets
    ):
        yield boto3


class TestS3Result:
    def test_s3_client_init_uses_secrets(self, mock_boto3):
        result = S3Result(bucket="bob")
        assert result.bucket == "bob"
        assert mock_boto3.client.called is False

        assert result.client is not None

        assert mock_boto3.client.call_args[1] == {
            "aws_access_key_id": "access_key",
            "aws_session_token": None,
            "aws_secret_access_key": "secret_access_key",
            "region_name": None,
        }

    def test_forwards_boto3_kwargs(self, mock_boto3):
        result = S3Result(bucket="mybucket", boto3_kwargs={"region_name": "a-region"})
        assert result.client is not None

        assert mock_boto3.client.call_args[1] == {
            "aws_access_key_id": "access_key",
            "aws_session_token": None,
            "aws_secret_access_key": "secret_access_key",
            "region_name": "a-region",
        }

    def test_s3_writes_to_blob_with_rendered_filename(self, mock_boto3):
        result = S3Result(bucket="foo", location="{thing}/here.txt")

        with prefect.context(thing="yes!"):
            new_result = result.write("so-much-data", **prefect.context)

        used_uri = mock_boto3.client.return_value.upload_fileobj.call_args[1]["Key"]

        assert used_uri == new_result.location
        assert new_result.location.startswith("yes!/here.txt")

    def test_s3_result_is_pickleable(self, mock_boto3):
        class NoPickle:
            def __getstate__(self):
                raise ValueError("I cannot be pickled.")

        mock_boto3.client.return_value = NoPickle()

        result = S3Result(bucket="foo")
        assert result.client is not None

        res = cloudpickle.loads(cloudpickle.dumps(result))
        assert isinstance(res, S3Result)

    def test_s3_result_does_not_exist(self, mock_boto3):
        import botocore

        exc = botocore.exceptions.ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "list_objects"
        )
        mock_boto3.client.return_value.get_object.side_effect = exc

        result = S3Result(bucket="bob", location="stuff")
        result = result.format()
        assert result.exists("stuff") is False

    def test_s3_result_exists(self, mock_boto3):
        result = S3Result(bucket="bob", location="stuff")
        result = result.format()
        assert result.exists("stuff") is True
