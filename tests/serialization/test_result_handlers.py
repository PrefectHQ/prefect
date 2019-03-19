import pytest

from unittest.mock import MagicMock, patch

from prefect.client import Client
from prefect.engine.cloud.result_handler import CloudResultHandler
from prefect.engine.result_handlers import (
    ResultHandler,
    JSONResultHandler,
    GCSResultHandler,
    LocalResultHandler,
)
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.utilities.configuration import set_temporary_config


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


class TestCloudResultHandler:
    def test_serialize_with_no_attributes(self):
        with set_temporary_config({"cloud.result_handler": "website"}):
            serialized = ResultHandlerSchema().dump(CloudResultHandler())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "CloudResultHandler"
        assert serialized["result_handler_service"] == "website"
        assert "client" not in serialized

    def test_serialize_with_attributes(self):
        handler = CloudResultHandler(result_handler_service="http://foo.bar")
        handler.client = Client()
        serialized = ResultHandlerSchema().dump(handler)
        assert isinstance(serialized, dict)
        assert serialized["type"] == "CloudResultHandler"
        assert serialized["result_handler_service"] == "http://foo.bar"
        assert "client" not in serialized

    def test_deserialize_cloud_result_handler(self):
        schema = ResultHandlerSchema()
        handler = CloudResultHandler(result_handler_service="http://foo.bar")
        handler._client = Client()
        obj = schema.load(schema.dump(handler))
        assert isinstance(obj, CloudResultHandler)
        assert hasattr(obj, "logger")
        assert obj.logger.name == "prefect.CloudResultHandler"
        assert obj.result_handler_service == "http://foo.bar"
        assert obj._client is None

    def test_deserialize_cloud_result_handler_with_None_populates_from_config(self):
        schema = ResultHandlerSchema()
        handler = CloudResultHandler()
        handler.result_handler_service = None
        handler._client = Client()
        serialized = schema.dump(handler)
        with set_temporary_config({"cloud.result_handler": "new-service"}):
            obj = schema.load(serialized)
        assert isinstance(obj, CloudResultHandler)
        assert hasattr(obj, "logger")
        assert obj.logger.name == "prefect.CloudResultHandler"
        assert obj.result_handler_service == "new-service"
        assert obj._client is None


@pytest.mark.xfail(raises=ImportError)
class TestGCSResultHandler:
    @pytest.fixture
    def google_client(self, monkeypatch):
        with patch.dict("sys.modules", {"google.cloud": MagicMock()}):
            yield

    def test_serialize(self, google_client):
        handler = GCSResultHandler(bucket="my-bucket")
        serialized = ResultHandlerSchema().dump(handler)
        assert serialized["type"] == "GCSResultHandler"
        assert serialized["bucket"] == "my-bucket"

    def test_deserialize_from_dict(self, google_client):
        handler = ResultHandlerSchema().load(
            {"type": "GCSResultHandler", "bucket": "foo-bar"}
        )
        assert isinstance(handler, GCSResultHandler)
        assert handler.bucket == "foo-bar"

    def test_roundtrip(self, google_client):
        schema = ResultHandlerSchema()
        handler = schema.load(schema.dump(GCSResultHandler(bucket="bucket3")))
        assert isinstance(handler, GCSResultHandler)
        assert handler.bucket == "bucket3"


class TestJSONResultHandler:
    def test_serialize(self):
        serialized = ResultHandlerSchema().dump(JSONResultHandler())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "JSONResultHandler"

    def test_deserialize_from_dict(self):
        handler = ResultHandlerSchema().load({"type": "JSONResultHandler"})
        assert isinstance(handler, JSONResultHandler)

    def test_roundtrip(self):
        schema = ResultHandlerSchema()
        handler = schema.load(schema.dump(JSONResultHandler()))
        assert isinstance(handler, JSONResultHandler)
        assert handler.write(3) == "3"
