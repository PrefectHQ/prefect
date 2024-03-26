import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import model_dump


def test_model_dump():
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    assert model_dump(model) == {"a": 1, "b": "2"}


def test_model_dump_with_flag_disabled():
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    assert model_dump(model) == {"a": 1, "b": "2"}


def test_model_dump_with_non_basemodel_raises():
    with pytest.raises(TypeError, match="Expected a Pydantic model"):
        model_dump("not a model")  # type: ignore
