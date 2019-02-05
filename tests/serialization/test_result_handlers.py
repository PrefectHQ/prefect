import pytest

from prefect.client import Client
from prefect.engine.cloud.result_handler import CloudResultHandler
from prefect.engine.result_handlers import ResultHandler, LocalResultHandler
from prefect.serialization.result_handlers import ResultHandlerSchema


class TestLocalResultHandler:
    def test_serialize_local_result_handler_with_no_dir(self):
        serialized = ResultHandlerSchema().dump(LocalResultHandler())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "LocalResultHandler"
        assert serialized["dir"] is None

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
        serialized = ResultHandlerSchema().dump(CloudResultHandler())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "CloudResultHandler"
        assert serialized["result_handler_service"] is None
        assert "client" not in serialized

    def test_serialize_with_attributes(self):
        handler = CloudResultHandler(result_handler_service="http://foo.bar")
        handler.client = Client()
        serialized = ResultHandlerSchema().dump(handler)
        assert isinstance(serialized, dict)
        assert serialized["type"] == "CloudResultHandler"
        assert serialized["result_handler_service"] == "http://foo.bar"
        assert "client" not in serialized

    @pytest.mark.parametrize("result_handler_service", [None, "http://foo.bar"])
    def test_deserialize_cloud_result_handler(self, result_handler_service):
        schema = ResultHandlerSchema()
        handler = CloudResultHandler(result_handler_service=result_handler_service)
        handler._client = Client()
        obj = schema.load(schema.dump(handler))
        assert isinstance(obj, CloudResultHandler)
        assert hasattr(obj, "logger")
        assert obj.logger.name == "prefect.CloudResultHandler"
        assert obj.result_handler_service == result_handler_service
        assert obj._client is None
