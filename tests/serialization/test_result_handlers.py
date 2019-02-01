import pytest

from prefect.client import Client
from prefect.engine.cloud.result_serializer import CloudResultSerializer
from prefect.engine.result_serializers import ResultSerializer, LocalResultSerializer
from prefect.serialization.result_serializers import ResultSerializerSchema


class TestBaseResultSerializer:
    def test_serialize_base_result_serializer(self):
        serialized = ResultSerializerSchema().dump(ResultSerializer())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "ResultSerializer"

    def test_deserialize_base_result_serializer(self):
        schema = ResultSerializerSchema()
        obj = schema.load(schema.dump(ResultSerializer()))
        assert isinstance(obj, ResultSerializer)
        assert hasattr(obj, "logger")
        assert obj.logger.name == "prefect.ResultSerializer"


class TestLocalResultSerializer:
    def test_serialize_local_result_serializer_with_no_dir(self):
        serialized = ResultSerializerSchema().dump(LocalResultSerializer())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "LocalResultSerializer"
        assert serialized["dir"] is None

    def test_serialize_local_result_serializer_with_dir(self):
        serialized = ResultSerializerSchema().dump(
            LocalResultSerializer(dir="/root/prefect")
        )
        assert isinstance(serialized, dict)
        assert serialized["type"] == "LocalResultSerializer"
        assert serialized["dir"] == "/root/prefect"

    @pytest.mark.parametrize("dir", [None, "/root/prefect"])
    def test_deserialize_local_result_serializer(self, dir):
        schema = ResultSerializerSchema()
        obj = schema.load(schema.dump(LocalResultSerializer(dir=dir)))
        assert isinstance(obj, LocalResultSerializer)
        assert hasattr(obj, "logger")
        assert obj.logger.name == "prefect.LocalResultSerializer"
        assert obj.dir == dir


class TestCloudResultSerializer:
    def test_serialize_with_no_attributes(self):
        serialized = ResultSerializerSchema().dump(CloudResultSerializer())
        assert isinstance(serialized, dict)
        assert serialized["type"] == "CloudResultSerializer"
        assert serialized["result_serializer_service"] is None
        assert "client" not in serialized

    def test_serialize_with_attributes(self):
        handler = CloudResultSerializer(result_serializer_service="http://foo.bar")
        handler.client = Client()
        serialized = ResultSerializerSchema().dump(handler)
        assert isinstance(serialized, dict)
        assert serialized["type"] == "CloudResultSerializer"
        assert serialized["result_serializer_service"] == "http://foo.bar"
        assert "client" not in serialized

    @pytest.mark.parametrize("result_serializer_service", [None, "http://foo.bar"])
    def test_deserialize_local_result_serializer(self, result_serializer_service):
        schema = ResultSerializerSchema()
        handler = CloudResultSerializer(
            result_serializer_service=result_serializer_service
        )
        handler.client = Client()
        obj = schema.load(schema.dump(handler))
        assert isinstance(obj, CloudResultSerializer)
        assert hasattr(obj, "logger")
        assert obj.logger.name == "prefect.CloudResultSerializer"
        assert obj.result_serializer_service == result_serializer_service
        assert obj.client is None
