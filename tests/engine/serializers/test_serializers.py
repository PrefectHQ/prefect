import pytest
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

    def test_serialize_returns_cloudpickle(self):
        value = ["abc", 123, pendulum.now()]
        serialized = Serializer().serialize(value)
        deserialized = cloudpickle.loads(serialized)
        assert deserialized == value

    def test_serialize_with_base64_encoded_cloudpickle(self):
        # for backwards compatibility, ensure encoded cloudpickles are
        # deserialized
        value = ["abc", 123, pendulum.now()]
        serialized = base64.b64encode(cloudpickle.dumps(value))
        deserialized = Serializer().deserialize(serialized)
        assert deserialized == value

    def test_meaningful_errors_are_raised(self):
        # when deserialization fails, show the original error, not the
        # backwards-compatible error
        with pytest.raises(cloudpickle.pickle.UnpicklingError, match="stack underflow"):
            Serializer().deserialize(b"bad-bytes")


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
