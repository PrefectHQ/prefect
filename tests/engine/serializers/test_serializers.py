import base64
import json

import cloudpickle
import pendulum

from prefect.engine.serializers import JSONSerializer, Serializer, DateTimeSerializer


def test_equality():
    assert Serializer() == Serializer()
    assert JSONSerializer() == JSONSerializer()
    assert Serializer() != JSONSerializer()


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


class TestDateTimeSerializer:
    def test_serialize_returns_bytes(self):
        dt = pendulum.now()
        serialized = DateTimeSerializer().serialize(dt)
        assert isinstance(serialized, bytes)

    def test_serialize_string(self):
        serialized = DateTimeSerializer().serialize("2020-01-01")
        assert serialized == b"2020-01-01T00:00:00Z"

    def test_serialize_in_utc(self):
        serialized = DateTimeSerializer().serialize(
            pendulum.datetime(2020, 1, 1).in_tz("EST")
        )
        assert serialized == b"2020-01-01T00:00:00Z"

    def test_serialize_none(self):
        assert DateTimeSerializer().serialize(None) == b""

    def test_deserialize_none(self):
        serialized = DateTimeSerializer().serialize(None)
        assert DateTimeSerializer().deserialize(serialized) is None

    def test_deserialize_returns_objects(self):
        dt = pendulum.now()
        serialized = DateTimeSerializer().serialize(dt)
        deserialized = DateTimeSerializer().deserialize(serialized)
        assert deserialized == dt
