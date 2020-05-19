import marshmallow
import pytest

import prefect
from prefect.engine.result import NoResult, NoResultType, Result, SafeResult
from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.serialization.result import (
    NoResultSchema,
    SafeResultSchema,
    StateResultSchema,
)


def test_basic_safe_result_serializes():
    res = SafeResult("3", result_handler=JSONResultHandler())
    serialized = SafeResultSchema().dump(res)
    assert serialized["__version__"] == prefect.__version__
    assert serialized["value"] == "3"
    assert serialized["result_handler"]["type"] == "JSONResultHandler"


def test_basic_noresult_serializes():
    r = NoResult
    handled = NoResultSchema().dump(r)
    version = handled.pop("__version__")
    assert version == prefect.__version__
    assert handled == {}


def test_basic_safe_result_deserializes():
    r = SafeResultSchema().load(
        {"value": "3", "result_handler": {"type": "JSONResultHandler"}}
    )
    assert isinstance(r, SafeResult)
    assert r.value == "3"
    assert r.result_handler == JSONResultHandler()


def test_safe_result_with_custom_handler_deserializes():
    r = SafeResultSchema().load(
        {"value": "3", "result_handler": {"type": "CustomResultHandler"}}
    )
    assert isinstance(r, SafeResult)
    assert r.value == "3"
    assert isinstance(r.result_handler, ResultHandler)


def test_roundtrip_for_results():
    r = SafeResult(value={"y": 4}, result_handler=JSONResultHandler())
    s = SafeResultSchema().load(SafeResultSchema().dump(r))
    assert r == s


def test_basic_noresult_deserializes():
    r = NoResultSchema().load({})
    assert r == NoResult
    assert isinstance(r, NoResultType)


def test_safe_result_serializes_result_handlers():
    r = SafeResult(value=3, result_handler=JSONResultHandler())
    handled = SafeResultSchema().dump(r)
    assert handled["result_handler"]["type"] == "JSONResultHandler"


def test_result_allows_none_value():
    schema = SafeResultSchema()
    r = SafeResult(value=None, result_handler=JSONResultHandler())
    handled = schema.load(schema.dump(r))
    assert handled.value is None
    assert handled.result_handler == JSONResultHandler()


def test_safe_result_disallows_none_result_handler_at_deserialization_time():
    schema = SafeResultSchema()
    r = SafeResult(value=None, result_handler=None)
    serialized = schema.dump(r)
    with pytest.raises(marshmallow.exceptions.ValidationError):
        schema.load(serialized)


@pytest.mark.parametrize(
    "obj", [SafeResult(value=19, result_handler=JSONResultHandler()), NoResult]
)
def test_state_result_schema_chooses_schema(obj):
    schema = StateResultSchema()
    assert type(schema.load(schema.dump(obj))) == type(obj)


def test_value_raises_error_on_dump_if_not_valid_json():
    r = SafeResult(
        value={"x": {"y": {"z": lambda: 1}}}, result_handler=JSONResultHandler()
    )
    with pytest.raises(marshmallow.exceptions.ValidationError):
        StateResultSchema().dump(r)
