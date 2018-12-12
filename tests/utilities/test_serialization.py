import datetime
import json

import marshmallow
import pendulum
import pytest

from prefect.utilities.collections import DotDict
from prefect.utilities.serialization import Bytes, DateTime, JSONCompatible, Nested

json_test_values = [
    1,
    [1, 2],
    "1",
    [1, "2"],
    {"x": 1},
    {"x": "1", "y": {"z": 3}},
    DotDict({"x": "1", "y": [DotDict(z=3)]}),
]


class Child(marshmallow.Schema):
    x = marshmallow.fields.String()


def get_child(obj, context):
    if obj.get("child key") is False:
        return marshmallow.missing
    else:
        return obj.get("child key", {"x": -1})


class TestNestedField:
    class Schema(marshmallow.Schema):
        child = Nested(Child, value_selection_fn=get_child)

    def test_nested_calls_value_selection_fn(self):
        assert self.Schema().dump({"child key": {"x": 42}}) == {"child": {"x": "42"}}

    def test_nested_calls_value_selection_fn_if_key_is_missing(self):
        assert self.Schema().dump({}) == {"child": {"x": "-1"}}

    def test_nested_respects_missing(self):
        assert self.Schema().dump({"child key": False}) == {}


class TestJSONCompatibleField:
    class Schema(marshmallow.Schema):
        j = JSONCompatible()

    @pytest.mark.parametrize("value", json_test_values)
    def test_json_serialization(self, value):
        serialized = self.Schema().dump({"j": value})
        assert serialized["j"] == value

    @pytest.mark.parametrize("value", json_test_values)
    def test_json_deserialization(self, value):
        serialized = self.Schema().load({"j": value})
        assert serialized["j"] == value

    def test_validate_on_dump(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().dump({"j": lambda: 1})

    def test_validate_on_load(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().load({"j": lambda: 1})


class TestDateTimeField:
    class Schema(marshmallow.Schema):
        dt = DateTime()
        dt_none = DateTime(allow_none=True)

    def test_datetime_serialize(self):

        dt = pendulum.datetime(2020, 1, 1, 6, tz="EST")
        serialized = self.Schema().dump(dict(dt=dt))
        assert serialized["dt"] != str(dt)
        assert serialized["dt"] == str(dt.in_tz("utc"))

    def test_datetime_deserialize(self):

        dt = datetime.datetime(2020, 1, 1, 6)
        serialized = self.Schema().load(dict(dt=str(dt)))
        assert isinstance(serialized["dt"], pendulum.DateTime)
        assert serialized["dt"].tz == pendulum.tz.UTC

    def test_serialize_datetime_none(self):
        serialized = self.Schema().dump(dict(dt=None))
        assert serialized["dt"] is None

    def test_deserialize_datetime_none(self):
        deserialized = self.Schema().load(dict(dt_none=None))
        assert deserialized["dt_none"] is None


class TestBytesField:
    class Schema(marshmallow.Schema):
        b = Bytes()
        b_none = Bytes(allow_none=True)

    def test_bytes_serialize(self):
        serialized = self.Schema().dump(dict(b=b"hello"))
        assert serialized["b"] == "aGVsbG8="

    def test_bytes_deserialize(self):
        serialized = self.Schema().load(dict(b="aGVsbG8="))
        assert serialized["b"] == b"hello"

    def test_bytes_serialize_none(self):
        serialized = self.Schema().dump(dict(b=None))
        assert serialized["b"] is None

    def test_bytes_deserialize_none(self):
        serialized = self.Schema().load(dict(b_none=None))
        assert serialized["b_none"] is None
