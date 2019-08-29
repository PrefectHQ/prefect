from unittest.mock import MagicMock, patch

import pytest

import prefect
from prefect.client import Client
from prefect.engine.result_handlers import (
    GCSResultHandler,
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
    S3ResultHandler,
    AzureResultHandler,
)
from prefect.serialization.result_handlers import (
    CustomResultHandlerSchema,
    ResultHandlerSchema,
)
from prefect.utilities.configuration import set_temporary_config


class TestCustomSchema:
    def test_custom_schema_dump_on_dummy_class(self):
        class Dummy(ResultHandler):
            def read(self, *args, **kwargs):
                pass

            def write(self, *args, **kwargs):
                pass

        serialized = CustomResultHandlerSchema().dump(Dummy())
        assert serialized["type"].endswith("Dummy")
        assert serialized["__version__"] == prefect.__version__

    def test_custom_schema_dump_on_stateful_class(self):
        class Stateful(ResultHandler):
            def __init__(self, x):
                self.x = x

            def read(self, *args, **kwargs):
                pass

            def write(self, *args, **kwargs):
                pass

        serialized = CustomResultHandlerSchema().dump(Stateful(42))
        assert serialized["type"].endswith("Stateful")
        assert serialized["__version__"] == prefect.__version__

    def test_custom_schema_roundtrip_on_base_class(self):
        class Dummy(ResultHandler):
            def read(self, *args, **kwargs):
                pass

            def write(self, *args, **kwargs):
                pass

        schema = CustomResultHandlerSchema()
        obj = schema.load(schema.dump(Dummy()))
        assert obj is None

    def test_custom_schema_roundtrip_on_stateful_class(self):
        class Stateful(ResultHandler):
            def __init__(self, x):
                self.x = x

            def read(self, *args, **kwargs):
                pass

            def write(self, *args, **kwargs):
                pass

        schema = CustomResultHandlerSchema()
        obj = schema.load(schema.dump(Stateful(42)))
        assert obj is None

    def test_result_handler_schema_defaults_to_custom(self):
        class Weird(ResultHandler):
            def __init__(self, y):
                self.y = y

            def read(self, *args, **kwargs):
                return 99

            def write(self, *args, **kwargs):
                return type(None)

        schema = ResultHandlerSchema()
        serialized = schema.dump(Weird(dict(y="test")))
        assert serialized["type"].endswith("Weird")
        assert serialized["__version__"] == prefect.__version__

        obj = schema.load(serialized)
        assert obj is None


class TestLocalResultHandler:
    def test_serialize_local_result_handler_with_no_dir(self):
        serialized = ResultHandlerSchema().dump(LocalResultHandler())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "LocalResultHandler"
        assert serialized["dir"] is None

    def test_deserialize_from_dict(self):
        handler = ResultHandlerSchema().load({"type": "LocalResultHandler"})
        assert isinstance(handler, LocalResultHandler)
        assert handler.dir is None

    def test_serialize_local_result_handler_with_dir(self):
        serialized = ResultHandlerSchema().dump(LocalResultHandler(dir="/root/prefect"))
        assert isinstance(serialized, dict)
        assert serialized["type"] == "LocalResultHandler"
        assert serialized["dir"] == "/root/prefect"

    @pytest.mark.parametrize("dir", [None, "/root/prefect"])
    def test_deserialize_local_result_handler(self, dir):
        schema = ResultHandlerSchema()
        obj = schema.load(schema.dump(LocalResultHandler(dir=dir)))
        assert isinstance(obj, LocalResultHandler)
        assert hasattr(obj, "logger")
        assert obj.logger.name == "prefect.LocalResultHandler"
        assert obj.dir == dir


@pytest.mark.xfail(raises=ImportError, reason="google extras not installed.")
class TestGCSResultHandler:
    def test_serialize(self):
        handler = GCSResultHandler(bucket="my-bucket", credentials_secret="FOO")
        serialized = ResultHandlerSchema().dump(handler)
        assert serialized["type"] == "GCSResultHandler"
        assert serialized["bucket"] == "my-bucket"
        assert serialized["credentials_secret"] == "FOO"

    def test_deserialize_from_dict(self):
        handler = ResultHandlerSchema().load(
            {"type": "GCSResultHandler", "bucket": "foo-bar"}
        )
        assert isinstance(handler, GCSResultHandler)
        assert handler.bucket == "foo-bar"
        assert handler.credentials_secret == "GOOGLE_APPLICATION_CREDENTIALS"

    def test_roundtrip(self):
        schema = ResultHandlerSchema()
        handler = schema.load(schema.dump(GCSResultHandler(bucket="bucket3")))
        assert isinstance(handler, GCSResultHandler)
        assert handler.bucket == "bucket3"

    def test_roundtrip_never_loads_client(self, monkeypatch):
        schema = ResultHandlerSchema()

        def raise_me(*args, **kwargs):
            raise SyntaxError("oops")

        monkeypatch.setattr(GCSResultHandler, "initialize_client", raise_me)
        handler = schema.load(
            schema.dump(GCSResultHandler(bucket="bucket3", credentials_secret="FOO"))
        )
        assert isinstance(handler, GCSResultHandler)
        assert handler.bucket == "bucket3"
        assert handler.credentials_secret == "FOO"


class TestJSONResultHandler:
    def test_serialize(self):
        serialized = ResultHandlerSchema().dump(JSONResultHandler())
        assert isinstance(serialized, dict)

    def test_deserialize_from_dict(self):
        handler = ResultHandlerSchema().load({"type": "JSONResultHandler"})
        assert isinstance(handler, JSONResultHandler)

    def test_roundtrip(self):
        schema = ResultHandlerSchema()
        handler = schema.load(schema.dump(JSONResultHandler()))
        assert isinstance(handler, JSONResultHandler)
        assert handler.write(3) == "3"


@pytest.mark.xfail(raises=ImportError, reason="aws extras not installed.")
class TestS3ResultHandler:
    def test_serialize(self):
        handler = S3ResultHandler(bucket="my-bucket", aws_credentials_secret="FOO")
        serialized = ResultHandlerSchema().dump(handler)
        assert serialized["type"] == "S3ResultHandler"
        assert serialized["bucket"] == "my-bucket"
        assert serialized["aws_credentials_secret"] == "FOO"

    def test_deserialize_from_dict(self):
        handler = ResultHandlerSchema().load(
            {"type": "S3ResultHandler", "bucket": "foo-bar"}
        )
        assert isinstance(handler, S3ResultHandler)
        assert handler.bucket == "foo-bar"
        assert handler.aws_credentials_secret == "AWS_CREDENTIALS"

    def test_roundtrip(self):
        schema = ResultHandlerSchema()
        handler = schema.load(schema.dump(S3ResultHandler(bucket="bucket3")))
        assert isinstance(handler, S3ResultHandler)
        assert handler.bucket == "bucket3"

    def test_roundtrip_never_loads_client(self, monkeypatch):
        schema = ResultHandlerSchema()

        def raise_me(*args, **kwargs):
            raise SyntaxError("oops")

        monkeypatch.setattr(S3ResultHandler, "initialize_client", raise_me)
        handler = schema.load(
            schema.dump(S3ResultHandler(bucket="bucket3", aws_credentials_secret="FOO"))
        )
        assert isinstance(handler, S3ResultHandler)
        assert handler.bucket == "bucket3"
        assert handler.aws_credentials_secret == "FOO"


@pytest.mark.xfail(raises=ImportError, reason="azure extras not installed.")
class TestAzureResultHandler:
    def test_serialize(self):
        handler = AzureResultHandler(
            container="my-container", azure_credentials_secret="FOO"
        )
        serialized = ResultHandlerSchema().dump(handler)
        assert serialized["type"] == "AzureResultHandler"
        assert serialized["container"] == "my-container"
        assert serialized["azure_credentials_secret"] == "FOO"

    def test_deserialize_from_dict(self):
        handler = ResultHandlerSchema().load(
            {"type": "AzureResultHandler", "container": "foo-bar"}
        )
        assert isinstance(handler, AzureResultHandler)
        assert handler.container == "foo-bar"
        assert handler.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_roundtrip(self):
        schema = ResultHandlerSchema()
        handler = schema.load(schema.dump(AzureResultHandler(container="container3")))
        assert isinstance(handler, AzureResultHandler)
        assert handler.container == "container3"

    def test_roundtrip_never_loads_client(self, monkeypatch):
        schema = ResultHandlerSchema()

        def raise_me(*args, **kwargs):
            raise SyntaxError("oops")

        monkeypatch.setattr(AzureResultHandler, "initialize_service", raise_me)
        handler = schema.load(
            schema.dump(
                AzureResultHandler(
                    container="container3", azure_credentials_secret="FOO"
                )
            )
        )
        assert isinstance(handler, AzureResultHandler)
        assert handler.container == "container3"
        assert handler.azure_credentials_secret == "FOO"
