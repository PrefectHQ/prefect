import marshmallow
import pytest

import prefect
from prefect.engine.result import Result, NoResult, NoResultType, SafeResult
from prefect.engine.result_handlers import JSONResultHandler
from prefect.serialization.result import (
    SafeResultSchema,
    NoResultSchema,
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


def test_basic_result_doesnt_serialize():
    r = Result(3)
    handled = StateResultSchema().dump(r)
    assert handled[1]["_schema"] == "Unsupported object type: Result"


def test_basic_safe_result_deserializes():
    r = ResultSchema().load({"value": "3"})
    assert isinstance(r, Result)
    assert r.value == "3"
    assert r.handled is False
    assert r.result_handler is None


def test_roundtrip_for_results():
    r = Result(value={"y": 4})
    s = ResultSchema().load(ResultSchema().dump(r))
    assert r == s


def test_basic_noresult_deserializes():
    r = NoResultSchema().load({})
    assert r == NoResult
    assert isinstance(r, NoResultType)


def test_result_serializes_result_handlers():
    r = Result(value=3, handled=False, result_handler=JSONResultHandler())
    handled = ResultSchema().dump(r)
    assert handled["result_handler"]["type"] == "JSONResultHandler"


def test_result_allows_none_value_and_handler():
    schema = ResultSchema()
    r = Result(value=None, result_handler=None)
    handled = schema.load(schema.dump(r))
    assert handled.value is None
    assert handled.result_handler is None


@pytest.mark.parametrize("obj", [Result(value=19), NoResult])
def test_state_result_schema_chooses_schema(obj):
    schema = StateResultSchema()
    assert type(schema.load(schema.dump(obj))) == type(obj)


def test_value_raises_error_on_dump_if_not_valid_json():
    r = Result(value={"x": {"y": {"z": lambda: 1}}})
    with pytest.raises(marshmallow.exceptions.ValidationError):
        StateResultSchema().dump(r)
