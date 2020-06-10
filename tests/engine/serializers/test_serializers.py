import base64
import json

import cloudpickle
import pendulum

from prefect.engine.serializers import JSONSerializer, Serializer


class TestSerializer:
    def test_serialize_returns_bytes(self):
        value = ["abc", 123, pendulum.now()]
        serialized = Serializer().serialize(value)
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects(self):
        value = ["abc", 123, pendulum.now()]
        serialized = Serializer().serialize(value)
        deserialized = Serializer().deserialize(serialized)
        assert deserialized == value

    def test_serialize_returns_base64_cloudpickle(self):
        value = ["abc", 123, pendulum.now()]
        serialized = Serializer().serialize(value)
        deserialized = cloudpickle.loads(base64.urlsafe_b64decode(serialized))
        assert deserialized == value


class TestJSONSerializer:
    def test_serialize_returns_bytes(self):
        value = ["abc", 123]
        serialized = JSONSerializer().serialize(value)
        assert isinstance(serialized, bytes)

    def test_deserialize_returns_objects(self):
        value = ["abc", 123]
        serialized = JSONSerializer().serialize(value)
        deserialized = JSONSerializer().deserialize(serialized)
        assert deserialized == value

    def test_serialize_returns_json(self):
        value = ["abc", 123]
        serialized = JSONSerializer().serialize(value)
        assert serialized == json.dumps(value).encode()


def test_equality():
    assert Serializer() == Serializer()
    assert JSONSerializer() == JSONSerializer()
    assert Serializer() != JSONSerializer()
