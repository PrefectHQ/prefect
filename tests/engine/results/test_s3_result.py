from unittest.mock import MagicMock, patch

import cloudpickle
import pytest

import prefect
from prefect.engine.results import S3Result
from prefect.utilities.configuration import set_temporary_config

pytest.importorskip("boto3")
pytest.importorskip("botocore")


class TestS3Result:
    @pytest.fixture
    def session(self, monkeypatch):
        import boto3

        session = MagicMock()
        boto = MagicMock(session=session)
        monkeypatch.setattr("prefect.utilities.aws.boto3", boto)
        yield session

    def test_s3_client_init_uses_secrets(self, session):
        result = S3Result(bucket="bob")
        assert result.bucket == "bob"
        assert session.Session().client.called is False

        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=42))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                result.initialize_client()
        assert session.Session().client.call_args[1] == {
            "aws_access_key_id": 1,
            "aws_session_token": None,
            "aws_secret_access_key": 42,
        }

    def test_s3_writes_to_blob_with_rendered_filename(self, session):
        result = S3Result(bucket="foo", location="{thing}/here.txt")

        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=42)),
            thing="yes!",
        ) as ctx:
            with set_temporary_config({"cloud.use_local_secrets": True}):
                new_result = result.write("so-much-data", **ctx)

        used_uri = session.Session().client.return_value.upload_fileobj.call_args[1][
            "Key"
        ]

        assert used_uri == new_result.location
        assert new_result.location.startswith("yes!/here.txt")

    def test_s3_upload_handles_client_error(self, session):
        result = S3Result(bucket="foo", location="{thing}/here.txt")

        from botocore.exceptions import ClientError

        used_uri = (
            session.Session().client.return_value.upload_fileobj.side_effect
        ) = ClientError({}, {})

        with pytest.raises(ClientError):
            with prefect.context(
                secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=42)),
                thing="yes!",
            ) as ctx:
                with set_temporary_config({"cloud.use_local_secrets": True}):
                    new_result = result.write("so-much-data", **ctx)

    def test_s3_result_reads_blob_none_on_eof(self, session):
        result = S3Result(bucket="foo", location="here.txt")

        with set_temporary_config({"cloud.use_local_secrets": True}):
            new_result = result.read("here.txt")

            download = session.Session().client.return_value.download_fileobj

            assert download.call_args[1]["Bucket"] == "foo"
            assert download.call_args[1]["Fileobj"]
            assert download.call_args[1]["Key"] == "here.txt"

            assert new_result.value == None

    def test_s3_result_reads_blob(self, session, monkeypatch):
        result = S3Result(bucket="foo", location="here.txt")

        monkeypatch.setattr(
            "prefect.engine.results.s3_result.S3Result.deserialize_from_bytes",
            MagicMock(return_value="data"),
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            new_result = result.read("here.txt")

            download = session.Session().client.return_value.download_fileobj

            assert download.call_args[1]["Bucket"] == "foo"
            assert download.call_args[1]["Fileobj"]
            assert download.call_args[1]["Key"] == "here.txt"

            assert new_result.value == "data"

    def test_s3_result_reads_blob_none(self, session):
        result = S3Result(bucket="foo", location="here.txt")

        with set_temporary_config({"cloud.use_local_secrets": True}):
            session.Session().client.return_value.download_fileobj.side_effect = (
                Exception()
            )

            with pytest.raises(Exception):
                new_result = result.read("here.txt")

    def test_s3_result_is_pickleable(self, monkeypatch):
        class client:
            def __init__(self, *args, **kwargs):
                pass

            def __getstate__(self):
                raise ValueError("I cannot be pickled.")

        import boto3

        with patch.dict("sys.modules", {"boto3": MagicMock()}):
            boto3.session.Session().client = client

            with prefect.context(
                secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=42))
            ):
                with set_temporary_config({"cloud.use_local_secrets": True}):
                    result = S3Result(bucket="foo")
            res = cloudpickle.loads(cloudpickle.dumps(result))
            assert isinstance(res, S3Result)

    def test_s3_result_does_not_exist(self, session):
        import botocore

        exc = botocore.exceptions.ClientError(
            {"Error": {"Code": "404"}}, "list_objects"
        )

        class _client:
            def __init__(self, *args, **kwargs):
                pass

            def get_object(self, *args, **kwargs):
                raise exc

        session.Session().client = _client
        result = S3Result(bucket="bob", location="stuff")
        result = result.format()
        assert result.exists("stuff") == False

    def test_s3_result_exists(self, session):
        import botocore

        exc = botocore.exceptions.ClientError(
            {"Error": {"Code": "404"}}, "list_objects"
        )

        class _client:
            def __init__(self, *args, **kwargs):
                pass

            def get_object(self, *args, **kwargs):
                return MagicMock()

        session.Session().client = _client
        result = S3Result(bucket="bob", location="stuff")
        result = result.format()
        assert result.exists("stuff") == True

    def test_s3_result_exists_handles_unknown_exception(self, session):
        session.Session().client.return_value.get_object.side_effect = Exception()
        result = S3Result(bucket="bob", location="stuff")
        result = result.format()
        with pytest.raises(Exception):
            result.exists("stuff")
