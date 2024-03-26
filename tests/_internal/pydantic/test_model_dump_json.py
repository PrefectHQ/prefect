import json

import pytest
from _pytest.logging import LogCaptureFixture
from pydantic import BaseModel

from prefect._internal.pydantic import HAS_PYDANTIC_V2, model_dump_json
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS,
    temporary_settings,
)


@pytest.fixture(autouse=True)
def enable_v2_internals():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: True}):
        yield


def test_model_dump_json(caplog: LogCaptureFixture):
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    json_string = model_dump_json(model)
    assert json.loads(json_string) == json.loads('{"a":1,"b":"2"}')

    if HAS_PYDANTIC_V2:
        assert (
            "Using Pydantic v2 compatibility layer for `model_dump_json`" in caplog.text
        )
    else:
        assert "Pydantic v2 is not installed." in caplog.text


def test_model_dump_json_with_flag_disabled(caplog: LogCaptureFixture):
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: False}):
        if HAS_PYDANTIC_V2:
            from pydantic.warnings import PydanticDeprecatedSince20

            with pytest.warns(PydanticDeprecatedSince20):
                json_string = model_dump_json(model)
        else:
            json_string = model_dump_json(model)
        assert json.loads(json_string) == json.loads('{"a":1,"b":"2"}')

    if HAS_PYDANTIC_V2:
        assert "Pydantic v2 compatibility layer is disabled" in caplog.text
    else:
        assert "Pydantic v2 is not installed." in caplog.text


def test_model_dump_json_with_non_basemodel_raises():
    with pytest.raises(TypeError, match="Expected a Pydantic model"):
        model_dump_json("not a model")  # type: ignore
