import marshmallow
import pytest

import prefect
from prefect.engine.result import Result, NoResult
from prefect.engine.result_serializers import JSONResultSerializer
from prefect.serialization.result import ResultSchema, NoResultSchema


def test_basic_result_serializes():
    r = Result(3)
    serialized = ResultSchema().dump(r)
    assert serialized["value"] == 3
    assert serialized["serializer"] is None
    assert serialized["serialized"] is False
    assert serialized["__version__"] == prefect.__version__


def test_basic_noresult_serializes():
    r = NoResult()
    serialized = ResultSchema().dump(r)
    version = serialized.pop("__version__")
    assert version == prefect.__version__
    assert serialized == {}


def test_basic_result_deserializes():
    r = ResultSchema().load({"value": "3"})
    assert isinstance(r, Result)
    assert r.value == "3"
    assert r.serialized is False
    assert r.serializer is None


def test_basic_noresult_deserializes():
    r = NoResultSchema().load({})
    assert isinstance(r, NoResult)


def test_result_serializes_serializers():
    r = Result(value=3, serialized=False, serializer=JSONResultSerializer())
    serialized = ResultSchema().dump(r)
    assert serialized["serializer"]["type"] == "JSONResultSerializer"
