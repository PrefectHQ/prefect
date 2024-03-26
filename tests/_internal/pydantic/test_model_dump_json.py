import json

import pytest
from _pytest.logging import LogCaptureFixture
from pydantic import BaseModel

from prefect._internal.pydantic import model_dump_json


def test_model_dump_json(caplog: LogCaptureFixture):
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    json_string = model_dump_json(model)
    assert json.loads(json_string) == json.loads('{"a":1,"b":"2"}')


def test_model_dump_json_with_flag_disabled(caplog: LogCaptureFixture):
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    json_string = model_dump_json(model)

    assert json.loads(json_string) == json.loads('{"a":1,"b":"2"}')


def test_model_dump_json_with_non_basemodel_raises():
    with pytest.raises(TypeError, match="Expected a Pydantic model"):
        model_dump_json("not a model")  # type: ignore
