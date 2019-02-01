import marshmallow
import pytest

import prefect
from prefect.engine.result import Result, NoResult, NoResultType
from prefect.engine.result_handlers import JSONResultHandler
from prefect.serialization.result import ResultSchema, NoResultSchema


def test_basic_result_serializes():
    r = Result(3)
    handled = ResultSchema().dump(r)
    assert handled["value"] == 3
    assert handled["result_handler"] is None
    assert handled["handled"] is False
    assert handled["__version__"] == prefect.__version__


def test_basic_noresult_serializes():
    r = NoResult
    handled = ResultSchema().dump(r)
    version = handled.pop("__version__")
    assert version == prefect.__version__
    assert handled == {}


def test_basic_result_deserializes():
    r = ResultSchema().load({"value": "3"})
    assert isinstance(r, Result)
    assert r.value == "3"
    assert r.handled is False
    assert r.result_handler is None


def test_basic_noresult_deserializes():
    r = NoResultSchema().load({})
    assert r == NoResult
    assert isinstance(r, NoResultType)


def test_result_serializes_result_handlers():
    r = Result(value=3, handled=False, result_handler=JSONResultHandler())
    handled = ResultSchema().dump(r)
    assert handled["result_handler"]["type"] == "JSONResultHandler"


def test_result_allows_none_value():
    r = Result(value=None)
    handled = ResultSchema().dump(r)
    assert handled["value"] is None
