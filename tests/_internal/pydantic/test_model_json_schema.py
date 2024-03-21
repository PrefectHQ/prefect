"""
Tests for `prefect._internal.pydantic.model_json_schema` function.
"""
import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import HAS_PYDANTIC_V2, model_json_schema
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS,
    temporary_settings,
)


@pytest.fixture(autouse=True)
def enable_v2_internals():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: True}):
        yield


def test_model_json_schema(caplog):
    class TestModel(BaseModel):
        a: int
        b: str

    schema = model_json_schema(TestModel)

    assert "properties" in schema
    assert "type" in schema and schema["type"] == "object"

    assert "a" in schema["properties"]
    assert "b" in schema["properties"]

    if HAS_PYDANTIC_V2:
        assert (
            "Using Pydantic v2 compatibility layer for `model_json_schema`"
            in caplog.text
        )
    else:
        assert "Pydantic v2 is not installed." in caplog.text


def test_model_json_schema_with_flag_disabled(caplog):
    class TestModel(BaseModel):
        a: int
        b: str

    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: False}):
        schema = model_json_schema(TestModel)

    assert "properties" in schema
    assert "type" in schema and schema["type"] == "object"

    assert "a" in schema["properties"]
    assert "b" in schema["properties"]

    if HAS_PYDANTIC_V2:
        assert "Pydantic v2 compatibility layer is disabled" in caplog.text
    else:
        assert "Pydantic v2 is not installed." in caplog.text
