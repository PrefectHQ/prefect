from datetime import datetime

import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import model_dump
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_dump():
    """with either:
        - v2 installed and compatibility layer enabled
        - or v1 installed

    everything should work without deprecation warnings
    """

    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    assert model_dump(model) == {"a": 1, "b": "2"}


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_dump_with_flag_disabled():
    """with v2 installed and compatibility layer disabled, we should see deprecation warnings"""
    from pydantic import PydanticDeprecatedSince20

    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    with pytest.warns(PydanticDeprecatedSince20):
        assert model_dump(model) == {"a": 1, "b": "2"}


def test_model_dump_with_non_basemodel_raises():
    with pytest.raises(AttributeError):
        model_dump("not a model")  # type: ignore


def test_model_dump_with_json_mode():
    class TestModel(BaseModel):
        a: int
        time: datetime

    model = TestModel(a=1, time=datetime.now())

    assert model_dump(model, mode="json") == {"a": 1, "time": model.time.isoformat()}
