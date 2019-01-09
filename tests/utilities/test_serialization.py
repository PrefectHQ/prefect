import json
import uuid

import marshmallow
import pytest

from prefect.utilities.collections import DotDict
from prefect.utilities.serialization import (
    UUID,
    Bytes,
    FunctionReference,
    JSONCompatible,
    Nested,
)

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


class TestUUIDField:
    class Schema(marshmallow.Schema):
        u = UUID()

    def test_serialize_uuid(self):
        u = uuid.uuid4()
        serialized = self.Schema().dump(dict(u=u))
        assert serialized["u"] == str(u)

    def test_serialize_str(self):
        u = str(uuid.uuid4())
        serialized = self.Schema().dump(dict(u=u))
        assert serialized["u"] == u

    def test_deserialize_uuid(self):
        u = uuid.uuid4()
        deserialized = self.Schema().load(dict(u=u))
        assert deserialized["u"] == str(u)

    def test_deserialize_str(self):
        u = str(uuid.uuid4())
        deserialized = self.Schema().load(dict(u=u))
        assert deserialized["u"] == u


def fn():
    return 42


def fn2():
    return -1


class TestFunctionReferenceField:
    class Schema(marshmallow.Schema):
        f = FunctionReference(valid_functions=[fn])
        f_allow_invalid = FunctionReference(valid_functions=[fn], reject_invalid=False)
        f_none = FunctionReference(valid_functions=[fn], allow_none=True)

    def test_serialize_fn(self):
        serialized = self.Schema().dump(dict(f=fn))
        assert serialized["f"] == "tests.utilities.test_serialization.fn"

    def test_serialize_invalid_fn(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().dump(dict(f=fn2))

    def test_serialize_invalid_fn_without_validation(self):
        serialized = self.Schema().dump(dict(f_allow_invalid=fn2))
        assert serialized["f_allow_invalid"] == "tests.utilities.test_serialization.fn2"

    def test_deserialize_fn(self):
        deserialized = self.Schema().load(self.Schema().dump(dict(f=fn)))
        assert deserialized["f"] is fn

    def test_deserialize_invalid_fn(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().load({"f": "hello"})

    def test_deserialize_invalid_fn_without_validation(self):
        deserialized = self.Schema().load(
            dict(f_allow_invalid="tests.utilities.test_serialization.fn2")
        )
        assert (
            deserialized["f_allow_invalid"] == "tests.utilities.test_serialization.fn2"
        )

    def test_serialize_none(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().dump({"f": None})
        assert self.Schema().dump({"f_none": None})["f_none"] is None

    def test_deserialize_none(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().load({"f": None})
        assert self.Schema().load({"f_none": None})["f_none"] is None
