import datetime
import pendulum
import prefect
import pytest
import marshmallow
from prefect.utilities.serialization import (
    VersionedSchema,
    version,
    VERSIONS,
    get_versioned_schema,
    to_qualified_name,
)


@pytest.fixture(autouse=True)
def clear_versions():
    VERSIONS.clear()


def test_register_addsto_qualified_name_to_VERSIONS():
    @version("1")
    class Schema(VersionedSchema):
        pass

    assert to_qualified_name(Schema) in VERSIONS
    assert list(VERSIONS[to_qualified_name(Schema)]) == ["1"]


def test_register_multiple_versions():
    @version("1")
    class Schema(VersionedSchema):
        pass

    v1 = Schema

    @version("2")
    class Schema(VersionedSchema):
        pass

    v2 = Schema

    assert to_qualified_name(v1) == to_qualified_name(v2)
    assert to_qualified_name(Schema) in VERSIONS
    assert set(VERSIONS[to_qualified_name(Schema)]) == {"1", "2"}
    assert VERSIONS[to_qualified_name(Schema)]["1"] is v1
    assert VERSIONS[to_qualified_name(Schema)]["2"] is v2


def test_get_versioned_schemas():
    @version("1")
    class Schema(VersionedSchema):
        pass

    v1 = Schema

    @version("2")
    class Schema(VersionedSchema):
        pass

    v2 = Schema

    assert get_versioned_schema(Schema(), version="1") is v1
    assert get_versioned_schema(Schema(), version="1.5") is v1
    assert get_versioned_schema(Schema(), version="2") is v2
    assert get_versioned_schema(Schema(), version="2.5") is v2


def testget_versioned_schemas_when_unregistered():
    class Schema(VersionedSchema):
        pass

    with pytest.raises(ValueError) as exc:
        get_versioned_schema(Schema(), version="1")
    assert "unregistered" in str(exc).lower()


def testget_versioned_schemas_when_version_doesnt_match():
    @version("1")
    class Schema(VersionedSchema):
        pass

    with pytest.raises(ValueError) as exc:
        get_versioned_schema(Schema(), version="0")
    assert "no versionschema was registered" in str(exc).lower()


def test_version_must_be_a_string():

    with pytest.raises(TypeError) as exc:
        version(1)
    assert "version must be a string" in str(exc).lower()


def test_cant_register_non_versioned_schemas():

    with pytest.raises(TypeError) as exc:

        @version("1")
        class Schema(marshmallow.Schema):
            pass

    assert "expected versionedschema" in str(exc).lower()


def test_schema_writes_version_when_serialized_and_removes_when_deserialized():
    @version("0")
    class Schema(VersionedSchema):
        x = marshmallow.fields.String()

    serialized = Schema().dump({"x": "1"})
    assert serialized == {"x": "1", "__version__": prefect.__version__}
    deserialized = Schema().load(serialized)
    assert deserialized == {"x": "1"}


def test_version_determines_which_schema_to_load():
    @version("2")
    class Schema(VersionedSchema):
        y = marshmallow.fields.Int()

    @version("1")
    class Schema(VersionedSchema):
        x = marshmallow.fields.String()

    serialized = {"y": 1}
    serialized_v1 = {"x": "hi", "__version__": "1"}
    serialized_v2 = {"y": 2, "__version__": "2"}
    serialized_v2_wrong_version = {"y": 2, "__version__": "1"}
    assert Schema().load(serialized_v1) == {"x": "hi"}
    assert Schema().load(serialized_v2) == {"y": 2}
    with pytest.raises(marshmallow.exceptions.ValidationError):
        Schema().load(serialized_v2_wrong_version) == {}


def test_no_version_uses_most_recent_version():
    @version("2")
    class Schema(VersionedSchema):
        y = marshmallow.fields.Int()

    @version("1")
    class Schema(VersionedSchema):
        x = marshmallow.fields.String()

    serialized = {"y": 1}
    assert Schema().load(serialized) == {"y": 1}


def test_version_determines_which_nested_schema_to_load():
    @version("2")
    class Schema(VersionedSchema):
        y = marshmallow.fields.Int()
        nested = marshmallow.fields.Nested("self")

    @version("1")
    class Schema(VersionedSchema):
        x = marshmallow.fields.String()

    serialized_v2 = {"y": 1, "nested": {"y": 1}}
    serialized_v2_v1 = {"y": 1, "nested": {"x": "hi", "__version__": "1"}}
    serialized_v2_v2 = {"y": 1, "nested": {"y": 1, "__version__": "2"}}
    assert Schema().load(serialized_v2) == {"y": 1, "nested": {"y": 1}}
    assert Schema().load(serialized_v2_v2) == {"y": 1, "nested": {"y": 1}}
    assert Schema().load(serialized_v2_v1) == {"y": 1, "nested": {"x": "hi"}}


def test_versions_inherit_init_args():
    @version("2")
    class Schema(VersionedSchema):
        y = marshmallow.fields.Int()

    @version("1")
    class Schema(VersionedSchema):
        x = marshmallow.fields.String()

    # the version 1 schema will pass the unknown=True kwarg to the version 2 schema when
    # it loads it
    assert Schema(unknown=True).load({"y": 1, "z": 3, "__version__": "2"})


def test_schema_creates_object():
    class TestObject:
        def __init__(self, x):
            self.x = x

    @version("0")
    class Schema(VersionedSchema):
        class Meta:
            object_class = TestObject

        x = marshmallow.fields.Int()

    deserialized = Schema().load({"x": "1"})
    assert isinstance(deserialized, TestObject)
    assert deserialized.x == 1


def test_schema_does_not_create_object():
    class TestObject:
        def __init__(self, x):
            self.x = x

    @version("0")
    class Schema(VersionedSchema):
        class Meta:
            object_class = TestObject

        x = marshmallow.fields.Int()

    deserialized = Schema().load({"x": "1"}, create_object=False)
    assert deserialized == {"x": 1}


def test_nested_schema_creates_object():
    class TestObject:
        def __init__(self, x, nested=None):
            self.x = x
            self.nested = nested

    @version("0")
    class Schema(VersionedSchema):
        class Meta:
            object_class = TestObject

        x = marshmallow.fields.Int()
        nested = marshmallow.fields.Nested("self", allow_none=True)

    deserialized = Schema().load({"x": "1", "nested": {"x": "2"}})
    assert isinstance(deserialized, TestObject)
    assert isinstance(deserialized.nested, TestObject)
    assert deserialized.nested.x == 2


def test_nested_schema_does_not_create_object():
    class TestObject:
        def __init__(self, y, nested=None):
            self.x = x
            self.nested = nested

    @version("0")
    class Schema(VersionedSchema):
        class Meta:
            object_class = TestObject

        x = marshmallow.fields.Int()
        nested = marshmallow.fields.Nested("self", allow_none=True)

    deserialized = Schema().load({"x": "1", "nested": {"x": "2"}}, create_object=False)
    assert deserialized == {"x": 1, "nested": {"x": 2}}


def test_schema_creates_object_with_lambda():
    @version("0")
    class Schema(VersionedSchema):
        class Meta:
            object_class = lambda: TestObject

        y = marshmallow.fields.Int()

    class TestObject:
        def __init__(self, y):
            self.y = y

    deserialized = Schema().load({"y": "1"})
    assert isinstance(deserialized, TestObject)
    assert deserialized.y == 1


def test_schema_doesnt_create_object_if_arg_is_false():
    class TestObject:
        def __init__(self, y):
            self.y = y

    @version("0")
    class Schema(VersionedSchema):
        class Meta:
            object_class = TestObject

        y = marshmallow.fields.Int()

    assert Schema().load({"y": 1}, create_object=False) == {"y": 1}


def test_schemas_dump_datetime_to_UTC():
    """
    Marshmallow always adds timezone info to datetimes.

    This may not be desireable, but for the moment it is part of marshmallow.
    """

    class Schema(marshmallow.Schema):
        dt = marshmallow.fields.DateTime()

    dt = datetime.datetime(2020, 1, 1)
    dt_with_tz = pendulum.datetime(2020, 1, 1)

    serialized_dt = Schema().dump({"dt": dt})
    assert serialized_dt["dt"] == "2020-01-01T00:00:00+00:00"
    assert Schema().load(serialized_dt)["dt"] == dt_with_tz


def test_nested_schemas_pass_context_on_load():
    @version("0")
    class Child(VersionedSchema):
        x = marshmallow.fields.Function(None, lambda x, context: context["x"])

    @version("0")
    class Parent(VersionedSchema):
        child = marshmallow.fields.Nested(Child)

        @marshmallow.pre_load
        def set_context(self, obj):
            self.context.update(x=5)
            return obj

    assert Parent().load({"child": {"x": 1}})["child"]["x"] == 5
