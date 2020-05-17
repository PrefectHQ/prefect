import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import cloudpickle
import pendulum
import pytest

import prefect
from prefect.client import Client
from prefect.engine.result_handlers import (
    AzureResultHandler,
    GCSResultHandler,
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
    S3ResultHandler,
    SecretResultHandler,
    ConstantResultHandler,
)
from prefect.utilities.configuration import set_temporary_config


class TestConstantResultHandler:
    def test_instantiates_with_value(self):
        handler = ConstantResultHandler(5)
        assert handler.value == 5

        handler = ConstantResultHandler(value=10)
        assert handler.value == 10

    def test_read_returns_value(self):
        handler = ConstantResultHandler("hello world")
        assert handler.read("this param isn't used") == "hello world"

    def test_write_doesnt_overwrite_value(self):
        handler = ConstantResultHandler("untouchable!")

        handler.write("a different value")
        assert handler.value == "untouchable!"
        assert handler.read("still unused") == "untouchable!"

    def test_write_returns_value(self):
        handler = ConstantResultHandler("constant value")

        output = handler.write("a different value")
        assert output == "'constant value'"

    def test_handles_none_as_constant(self):

        handler = ConstantResultHandler(None)
        assert handler.read("still not used") is None
        output = handler.write("also not used")
        assert output == "None"


class TestJSONHandler:
    def test_json_handler_initializes_with_no_args(self):
        handler = JSONResultHandler()

    @pytest.mark.parametrize("res", [42, "stringy", None])
    def test_json_handler_writes(self, res):
        handler = JSONResultHandler()
        blob = handler.write(res)
        assert isinstance(blob, str)

    @pytest.mark.parametrize("res", [42, "stringy", None])
    def test_json_handler_writes_and_reads(self, res):
        handler = JSONResultHandler()
        final = handler.read(handler.write(res))
        assert final == res

    def test_json_handler_raises_normally(self):
        handler = JSONResultHandler()
        with pytest.raises(TypeError):
            handler.write(type(None))

    def test_json_handler_is_pickleable(self):
        handler = JSONResultHandler()
        new = cloudpickle.loads(cloudpickle.dumps(handler))
        assert isinstance(new, JSONResultHandler)


class TestLocalHandler:
    @pytest.fixture(scope="class")
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_local_handler_initializes_with_no_args(self):
        handler = LocalResultHandler()
        assert handler.dir == os.path.join(prefect.config.home_dir, "results")

    def test_local_handler_initializes_with_dir(self):
        root_dir = os.path.abspath(os.sep)
        handler = LocalResultHandler(dir=root_dir)
        assert handler.dir == root_dir

    def test_local_handler_cleverly_redirects_prefect_defaults(self):
        handler = LocalResultHandler(dir=prefect.config.home_dir)
        assert handler.dir == os.path.join(prefect.config.home_dir, "results")

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_handler_writes_and_writes_to_dir(self, tmp_dir, res):
        handler = LocalResultHandler(dir=tmp_dir)
        fpath = handler.write(res)
        assert isinstance(fpath, str)
        assert os.path.basename(fpath).startswith("prefect-result")

        with open(fpath, "rb") as f:
            val = f.read()
        assert isinstance(val, bytes)

    @pytest.mark.parametrize("res", [42, "stringy", None, type(None)])
    def test_local_handler_writes_and_reads(self, tmp_dir, res):
        handler = LocalResultHandler(dir=tmp_dir)
        final = handler.read(handler.write(res))
        assert final == res

    def test_local_handler_is_pickleable(self):
        handler = LocalResultHandler(dir="root")
        new = cloudpickle.loads(cloudpickle.dumps(handler))
        assert isinstance(new, LocalResultHandler)


def test_result_handler_base_class_is_a_passthrough():
    handler = ResultHandler()
    assert handler.write("foo") is None
    assert handler.read(99) is None


@pytest.mark.xfail(raises=ImportError, reason="google extras not installed.")
class TestGCSResultHandler:
    @pytest.fixture
    def google_client(self, monkeypatch):
        import google.cloud.storage

        client_util = MagicMock()
        monkeypatch.setattr(
            "prefect.engine.result_handlers.gcs.get_storage_client", client_util
        )
        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS=42)):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                yield client_util

    def test_gcs_init(self, google_client):
        handler = GCSResultHandler(bucket="bob")
        assert handler.bucket == "bob"
        assert handler.credentials_secret == "GOOGLE_APPLICATION_CREDENTIALS"
        assert google_client.called is False
        handler.initialize_client()
        assert google_client.return_value.bucket.call_args[0][0] == "bob"

    def test_gcs_writes_to_blob_prefixed_by_date_suffixed_by_prefect(
        self, google_client
    ):
        bucket = MagicMock()
        google_client.return_value.bucket = MagicMock(return_value=bucket)
        handler = GCSResultHandler(bucket="foo")
        handler.write("so-much-data")
        assert bucket.blob.called
        assert bucket.blob.call_args[0][0].startswith(
            pendulum.now("utc").format("Y/M/D")
        )
        assert bucket.blob.call_args[0][0].endswith("prefect_result")

    def test_gcs_uses_custom_secret_name(self, google_client):
        handler = GCSResultHandler(bucket="foo", credentials_secret="TEST_SECRET")

        with prefect.context(secrets=dict(TEST_SECRET=94611)):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_client()

        assert google_client.call_args[1]["credentials"] == 94611

    def test_gcs_writes_binary_string(self, google_client):
        blob = MagicMock()
        google_client.return_value.bucket = MagicMock(
            return_value=MagicMock(blob=MagicMock(return_value=blob))
        )
        handler = GCSResultHandler(bucket="foo")
        handler.write(None)
        assert blob.upload_from_string.called
        assert isinstance(blob.upload_from_string.call_args[0][0], str)

    def test_gcs_handler_is_pickleable(self, google_client, monkeypatch):
        class gcs_bucket:
            def __init__(self, *args, **kwargs):
                pass

            def __getstate__(self):
                raise ValueError("I cannot be pickled.")

        handler = GCSResultHandler("foo")
        res = cloudpickle.loads(cloudpickle.dumps(handler))
        assert isinstance(res, GCSResultHandler)


@pytest.mark.xfail(raises=ImportError, reason="aws extras not installed.")
class TestS3ResultHandler:
    @pytest.fixture
    def session(self, monkeypatch):
        import boto3

        session = MagicMock()
        with patch.dict("sys.modules", {"boto3": MagicMock(session=session)}):
            yield session

    def test_s3_client_init_uses_secrets(self, session):
        handler = S3ResultHandler(
            bucket="bob", aws_credentials_secret="AWS_CREDENTIALS"
        )
        assert handler.bucket == "bob"
        assert session.Session().client.called is False

        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=42))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_client()
        assert session.Session().client.call_args[1] == {
            "aws_access_key_id": 1,
            "aws_secret_access_key": 42,
        }

    def test_s3_client_init_uses_custom_secrets(self, session):
        handler = S3ResultHandler(bucket="bob", aws_credentials_secret="MY_FOO")

        with prefect.context(
            secrets=dict(MY_FOO=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=999))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_client()

        assert handler.bucket == "bob"
        assert session.Session().client.call_args[1] == {
            "aws_access_key_id": 1,
            "aws_secret_access_key": 999,
        }

    def test_s3_writes_to_blob_prefixed_by_date_suffixed_by_prefect(self, session):
        handler = S3ResultHandler(bucket="foo")

        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=42))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                uri = handler.write("so-much-data")

        used_uri = session.Session().client.return_value.upload_fileobj.call_args[1][
            "Key"
        ]

        assert used_uri == uri
        assert used_uri.startswith(pendulum.now("utc").format("Y/M/D"))
        assert used_uri.endswith("prefect_result")

    def test_s3_handler_is_pickleable(self, monkeypatch):
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
                    handler = S3ResultHandler(bucket="foo")
            res = cloudpickle.loads(cloudpickle.dumps(handler))
            assert isinstance(res, S3ResultHandler)

    def test_s3_uninitialized_client(self, session):
        handler = S3ResultHandler(
            bucket="bob", aws_credentials_secret="AWS_CREDENTIALS"
        )
        assert handler.bucket == "bob"

        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=42)),
            boto3client="test",
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                assert handler.client is not None

    def test_s3_with_kwargs_invalid_service_name(self, session):
        with pytest.raises(AssertionError) as ex:
            handler = S3ResultHandler(
                bucket="bob",
                aws_credentials_secret="AWS_CREDENTIALS",
                boto3_kwargs=dict(service_name="s3"),
            )
        assert str(ex.value) == 'Changing the boto3 "service_name" is not permitted!'

    def test_s3_with_kwarg_overwrite_aws_keys(self, session):
        handler = S3ResultHandler(
            bucket="bob",
            aws_credentials_secret="AWS_CREDENTIALS",
            boto3_kwargs=dict(aws_access_key_id=123, aws_secret_access_key=456,),
        )
        assert (
            "aws_access_key_id" in handler.boto3_kwargs.keys()
        ), 'Missing "aws_access_key_id" in boto_kwargs'
        assert (
            "aws_secret_access_key" in handler.boto3_kwargs.keys()
        ), 'Missing "aws_secret_access_key" in boto_kwargs'
        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=999))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_client()

        assert handler.bucket == "bob"
        assert session.Session().client.call_args[1] == {
            "aws_access_key_id": 1,
            "aws_secret_access_key": 999,
        }

    def test_s3_with_kwargs_aws_keys(self, session):
        handler = S3ResultHandler(
            bucket="bob",
            boto3_kwargs=dict(aws_access_key_id=123, aws_secret_access_key=456,),
        )
        assert (
            "aws_access_key_id" in handler.boto3_kwargs.keys()
        ), 'Missing "aws_access_key_id" in boto_kwargs'
        assert (
            "aws_secret_access_key" in handler.boto3_kwargs.keys()
        ), 'Missing "aws_secret_access_key" in boto_kwargs'
        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=999))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_client()

        assert handler.bucket == "bob"
        assert session.Session().client.call_args[1] == {
            "aws_access_key_id": 123,
            "aws_secret_access_key": 456,
        }

    def test_s3_with_kwargs(self, session):
        from botocore.client import Config

        kw = dict(
            region_name="us-east-1",
            api_version="0.0.1",
            endpoint_url="https://minio.local/",
            config=Config(
                signature_version="s3v4",
                s3=dict(
                    region_name="us-east-1",
                    addressing_style="path",
                    inject_host_prefix=False,
                ),
            ),
        )
        handler = S3ResultHandler(
            bucket="bob", aws_credentials_secret="AWS_CREDENTIALS", boto3_kwargs=kw
        )
        with prefect.context(
            secrets=dict(AWS_CREDENTIALS=dict(ACCESS_KEY=1, SECRET_ACCESS_KEY=999))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_client()

        assert handler.bucket == "bob"
        kw.update(
            {"aws_access_key_id": 1, "aws_secret_access_key": 999,}
        )
        assert session.Session().client.call_args[1] == kw


@pytest.mark.xfail(raises=ImportError, reason="azure extras not installed.")
class TestAzureResultHandler:
    @pytest.fixture
    def azure_service(self, monkeypatch):
        import azure.storage.blob

        service = MagicMock()
        blob = MagicMock(BlockBlobService=service)
        storage = MagicMock(blob=blob)

        with patch.dict("sys.modules", {"azure": MagicMock(storage=storage)}):
            yield service

    def test_azure_service_init_uses_secrets_with_account_key(self, azure_service):
        handler = AzureResultHandler(container="bob")
        assert handler.container == "bob"
        assert azure_service.called is False

        with prefect.context(
            secrets=dict(AZ_CREDENTIALS=dict(ACCOUNT_NAME="1", ACCOUNT_KEY="42"))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_service()

        assert azure_service.call_args[1] == {
            "account_name": "1",
            "account_key": "42",
            "sas_token": None,
        }

    def test_azure_service_init_uses_secrets_with_sas_token(self, azure_service):
        handler = AzureResultHandler(container="bob")
        assert handler.container == "bob"
        assert azure_service.called is False

        with prefect.context(
            secrets=dict(AZ_CREDENTIALS=dict(ACCOUNT_NAME="1", SAS_TOKEN="24"))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_service()

        assert azure_service.call_args[1] == {
            "account_name": "1",
            "sas_token": "24",
            "account_key": None,
        }

    def test_azure_service_init_uses_custom_secrets(self, azure_service):
        handler = AzureResultHandler(container="bob", azure_credentials_secret="MY_FOO")

        with prefect.context(
            secrets=dict(MY_FOO=dict(ACCOUNT_NAME=1, ACCOUNT_KEY=999))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_service()

        assert handler.container == "bob"
        assert azure_service.call_args[1] == {
            "account_name": 1,
            "account_key": 999,
            "sas_token": None,
        }

    def test_azure_service_init_uses_connection_string_over_secret(self, azure_service):
        handler = AzureResultHandler(
            container="bob", azure_credentials_secret="MY_FOO", connection_string="TEST"
        )

        with prefect.context(
            secrets=dict(MY_FOO=dict(ACCOUNT_NAME=1, ACCOUNT_KEY=999))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                handler.initialize_service()

        assert handler.container == "bob"
        assert azure_service.call_args[1] == {
            "connection_string": "TEST",
        }

    def test_azure_service_writes_to_blob_prefixed_by_date_suffixed_by_prefect(
        self, azure_service
    ):
        handler = AzureResultHandler(container="foo")

        with prefect.context(
            secrets=dict(AZ_CREDENTIALS=dict(ACCOUNT_NAME=1, ACCOUNT_KEY=42))
        ):
            with set_temporary_config({"cloud.use_local_secrets": True}):
                uri = handler.write("so-much-data")

        used_uri = azure_service.return_value.create_blob_from_text.call_args[1][
            "blob_name"
        ]

        assert used_uri == uri
        assert used_uri.startswith(pendulum.now("utc").format("Y/M/D"))
        assert used_uri.endswith("prefect_result")

    def test_azure_service_handler_is_pickleable(self):
        class service:
            def __init__(self, *args, **kwargs):
                pass

            def __getstate__(self):
                raise ValueError("I cannot be pickled.")

        with patch.dict(
            "sys.modules", {"azure.storage.blob": MagicMock(BlockBlobService=service)}
        ):
            with prefect.context(
                secrets=dict(AZ_CREDENTIALS=dict(ACCOUNT_NAME=1, ACCOUNT_KEY=42))
            ):
                with set_temporary_config({"cloud.use_local_secrets": True}):
                    handler = AzureResultHandler(container="foo")
            res = cloudpickle.loads(cloudpickle.dumps(handler))
            assert isinstance(res, AzureResultHandler)


class TestSecretHandler:
    @pytest.fixture
    def secret_task(self):
        return prefect.tasks.secrets.PrefectSecret(name="test")

    def test_secret_handler_requires_secret_task_at_init(self):
        with pytest.raises(TypeError, match="missing 1 required position"):
            handler = SecretResultHandler()

    def test_secret_handler_initializes_with_secret_task(self, secret_task):
        handler = SecretResultHandler(secret_task=secret_task)
        assert isinstance(handler.secret_task, prefect.tasks.secrets.PrefectSecret)
        assert handler.secret_task.name == "test"

    @pytest.mark.parametrize("res", [42, "stringy", None, dict(blah=lambda x: None)])
    def test_secret_handler_writes_by_only_returning_name(self, res, secret_task):
        handler = SecretResultHandler(secret_task)
        out = handler.write(res)
        assert out == "test"

    @pytest.mark.parametrize("res", [42, "stringy", None])
    def test_secret_handler_writes_and_reads(self, res, secret_task):
        handler = SecretResultHandler(secret_task)
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(test=res)):
                final = handler.read(handler.write(res))
        assert final == res

    def test_secret_handler_can_use_any_secret_type(self):
        class MySecret(prefect.tasks.secrets.PrefectSecret):
            def run(self):
                return "boo"

        handler = SecretResultHandler(MySecret(name="foo"))
        assert handler.write(123089123) == "foo"
        assert handler.read(lambda x: None) == "boo"

    def test_secret_handler_is_pickleable(self, secret_task):
        handler = SecretResultHandler(secret_task)
        new = cloudpickle.loads(cloudpickle.dumps(handler))
        assert isinstance(new, SecretResultHandler)
