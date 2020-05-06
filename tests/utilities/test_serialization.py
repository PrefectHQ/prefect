import datetime
import itertools
import uuid

import marshmallow
import pendulum
import pytest
import pytz
from box import Box

import prefect
from prefect.utilities.serialization import (
    UUID,
    Bytes,
    DateTimeTZ,
    FunctionReference,
    JSONCompatible,
    Nested,
    ObjectSchema,
    OneOfSchema,
    StatefulFunctionReference,
)

json_test_values = [
    1,
    [1, 2],
    "1",
    [1, "2"],
    {"x": 1},
    {"x": "1", "y": {"z": 3}},
    Box({"x": "1", "y": [dict(z=3)]}),
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


class TestDateTimeTZField:

    test_dates = [
        pendulum.now("utc"),
        pendulum.now("America/New_York"),
        datetime.datetime(2000, 1, 1),
        datetime.datetime(2000, 1, 1, tzinfo=pytz.timezone("US/Arizona")),
        pendulum.datetime(2018, 3, 11, 9, tz="UTC"),
        pendulum.datetime(2018, 3, 11, 9, tz="America/New_York"),
        pendulum.datetime(2018, 3, 11, 9, tz="US/Arizona"),
    ]

    class Schema(marshmallow.Schema):
        dt = DateTimeTZ()

    @pytest.mark.parametrize("dt", test_dates)
    def test_serialize_datetime(self, dt):
        serialized = self.Schema().dump(dict(dt=dt))
        pdt = pendulum.instance(dt)
        expected = dict(dt=str(pdt.naive()), tz=pdt.tzinfo.name)
        assert serialized["dt"] == expected

    @pytest.mark.parametrize("dt", test_dates)
    def test_deserialize_datetime(self, dt):
        schema = self.Schema()
        deserialized = schema.load(schema.dump(dict(dt=dt)))
        assert deserialized["dt"] == pendulum.instance(dt)

    def test_deserialize_respects_dst(self):
        dt = pendulum.datetime(2018, 3, 11, tz="America/New_York")
        schema = self.Schema()
        deserialized_dt = schema.load(schema.dump(dict(dt=dt)))["dt"]
        assert deserialized_dt.add(hours=4).hour == 5


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


def outer(x, y, z):
    def inner(q):
        return x + y + z + q

    return inner


class TestStatefulFunctionReferenceField:
    class Schema(marshmallow.Schema):
        f = StatefulFunctionReference(valid_functions=[outer])
        f_allow_invalid = StatefulFunctionReference(
            valid_functions=[outer], reject_invalid=False
        )
        f_none = StatefulFunctionReference(valid_functions=[outer], allow_none=True)

    def test_serialize_outer_no_state(self):
        serialized = self.Schema().dump(dict(f=outer))
        assert serialized["f"]["fn"] == "tests.utilities.test_serialization.outer"
        assert not serialized["f"]["kwargs"]

    def test_serialize_outer_with_state(self):
        serialized = self.Schema().dump(dict(f=outer(x=1, y=2, z=99)))
        assert serialized["f"]["fn"] == "tests.utilities.test_serialization.outer"
        assert serialized["f"]["kwargs"] == {"x": 1, "y": 2, "z": 99}

    def test_serialize_invalid_fn(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().dump(dict(f=fn2))

    def test_serialize_invalid_fn_without_validation(self):
        serialized = self.Schema().dump(dict(f_allow_invalid=fn2))
        assert (
            serialized["f_allow_invalid"]["fn"]
            == "tests.utilities.test_serialization.fn2"
        )
        assert not serialized["f_allow_invalid"]["kwargs"]

    def test_deserialize_outer_no_state(self):
        deserialized = self.Schema().load(self.Schema().dump(dict(f=outer)))
        assert deserialized["f"] is outer

    def test_deserialize_outer_with_state(self):
        deserialized = self.Schema().load(
            self.Schema().dump(dict(f=outer(x=1, y=2, z=99)))
        )
        assert deserialized["f"](100) == outer(x=1, y=2, z=99)(100)

    def test_deserialize_outer_with_state_doesnt_mutate_payload(self):
        payload = self.Schema().dump(dict(f=outer(x=1, y=2, z=datetime.time(4))))
        deserialized = self.Schema().load(payload)
        assert payload["f"]["kwargs"]["x"] == 1
        assert payload["f"]["kwargs"]["y"] == 2
        assert isinstance(payload["f"]["kwargs"]["z"], str)

    def test_deserialize_invalid_fn(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().load({"f": {"fn": "hello"}})

    def test_deserialize_invalid_fn_without_validation(self):
        deserialized = self.Schema().load(
            dict(f_allow_invalid=dict(fn="tests.utilities.test_serialization.fn2"))
        )
        assert deserialized["f_allow_invalid"] is None

    def test_serialize_non_function_good_error(self):
        class Foo(object):
            def __call__(self, a, b):
                return a + b

        with pytest.raises(marshmallow.ValidationError, match="function required"):
            self.Schema().dump(dict(f=Foo()))

    def test_serialize_none(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().dump({"f": None})
        assert self.Schema().dump({"f_none": None})["f_none"] is None

    def test_deserialize_none(self):
        with pytest.raises(marshmallow.ValidationError):
            self.Schema().load({"f": None})
        assert self.Schema().load({"f_none": None})["f_none"] is None


class TestObjectSchema:
    def test_schema_writes_version_to_serialized_object(self):
        class TestObject:
            def __init__(self, x):
                self.x = x

        class Schema(ObjectSchema):
            class Meta:
                object_class = TestObject

            x = marshmallow.fields.Int()

        serialized = Schema().dump(TestObject(x=5))
        assert serialized == {"__version__": prefect.__version__, "x": 5}

    def test_schema_doesnt_mutate_object_on_load(self):
        class TestObject:
            def __init__(self, x):
                self.x = x

        class Schema(ObjectSchema):
            class Meta:
                object_class = TestObject

            x = marshmallow.fields.Int()

        serialized = Schema().dump(TestObject(x=5))

        Schema().load(serialized)
        assert serialized == {"__version__": prefect.__version__, "x": 5}

    def test_schema_creates_object(self):
        class TestObject:
            def __init__(self, x):
                self.x = x

        class Schema(ObjectSchema):
            class Meta:
                object_class = TestObject

            x = marshmallow.fields.Int()

        deserialized = Schema().load({"x": "1"})
        assert isinstance(deserialized, TestObject)
        assert deserialized.x == 1

    def test_schema_does_not_create_object_if_arg_is_false(self):
        class TestObject:
            def __init__(self, x):
                self.x = x

        class Schema(ObjectSchema):
            class Meta:
                object_class = TestObject

            x = marshmallow.fields.Int()

        deserialized = Schema().load({"x": "1"}, create_object=False)
        assert deserialized == {"x": 1}

    def test_schema_has_error_if_fields_cant_be_supplied_to_init(self):
        class TestObject:
            def __init__(self, x):
                self.x = x

        class Schema(ObjectSchema):
            class Meta:
                object_class = TestObject

            x = marshmallow.fields.Int()
            y = marshmallow.fields.Int()

        with pytest.raises(TypeError):
            Schema().load({"x": "1", "y": "2"})

    def test_schema_with_excluded_fields(self):
        class TestObject:
            def __init__(self, x):
                self.x = x

        class Schema(ObjectSchema):
            class Meta:
                object_class = TestObject
                exclude_fields = ["y"]

            x = marshmallow.fields.Int()
            y = marshmallow.fields.Int()

        deserialized = Schema().load({"x": "1", "y": "2"})
        assert isinstance(deserialized, TestObject)
        assert deserialized.x == 1
        assert not hasattr(deserialized, "y")

    def test_schema_creates_object_with_lambda(self):
        class Schema(ObjectSchema):
            class Meta:
                object_class = lambda: TestObject

            x = marshmallow.fields.Int()

        class TestObject:
            def __init__(self, x):
                self.x = x

        deserialized = Schema().load({"x": "1"})
        assert isinstance(deserialized, TestObject)
        assert deserialized.x == 1

    def test_schema_handles_unknown_fields(self):
        class TestObject:
            def __init__(self, x):
                self.x = x

        class Schema(ObjectSchema):
            class Meta:
                object_class = TestObject

            x = marshmallow.fields.Int()

        deserialized = Schema().load({"x": "1", "y": "2"})
        assert isinstance(deserialized, TestObject)
        assert not hasattr(deserialized, "y")


class TestOneOfSchema:
    def test_oneofschema_load_box(self):
        """
        Tests that modified OneOfSchema can load data from a Box (standard can not)
        """

        class ChildSchema(marshmallow.Schema):
            x = marshmallow.fields.Integer()

        class ParentSchema(OneOfSchema):
            type_schemas = {"Child": ChildSchema}

        child = ParentSchema().load(Box(type="Child", x="5"))
        assert child["x"] == 5

    def test_oneofschema_handles_unknown_fields(self):
        class ChildSchema(marshmallow.Schema):
            x = marshmallow.fields.Integer()

        class ParentSchema(OneOfSchema):
            type_schemas = {"Child": ChildSchema}

        child = ParentSchema().load(Box(type="Child", x="5", y="6"))
        assert child["x"] == 5
        assert not hasattr(child, "y")
