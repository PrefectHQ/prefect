import pytest
from _pytest.logging import LogCaptureFixture
from pydantic import BaseModel

from prefect._internal.pydantic import HAS_PYDANTIC_V2, model_copy
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS,
    temporary_settings,
)


@pytest.fixture(autouse=True)
def enable_v2_internals():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: True}):
        yield


def test_model_copy():
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")
    updated_model = model_copy(model, update={"a": 3}, deep=True)

    assert isinstance(updated_model, TestModel)
    assert updated_model.a == 3
    assert updated_model.b == "2"
    assert model.a == 1  # Original model should remain unchanged


def test_model_copy_with_flag_disabled(caplog: LogCaptureFixture):
    class TestModel(BaseModel):
        a: int
        b: str

    model = TestModel(a=1, b="2")

    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: False}):
        if HAS_PYDANTIC_V2:
            from pydantic.warnings import PydanticDeprecatedSince20

            with pytest.warns(PydanticDeprecatedSince20):
                updated_model = model_copy(model, update={"a": 3}, deep=True)
        else:
            updated_model = model_copy(model, update={"a": 3}, deep=True)

    assert isinstance(updated_model, TestModel)
    assert updated_model.a == 3
    assert updated_model.b == "2"
    assert model.a == 1  # Original model should remain unchanged

    if HAS_PYDANTIC_V2:
        assert "Pydantic v2 compatibility layer is disabled" in caplog.text
    else:
        assert "Pydantic v2 is not installed." in caplog.text


def test_model_copy_with_non_basemodel_raises():
    with pytest.raises(TypeError, match="Expected a Pydantic model"):
        model_copy("not a model")  # type: ignore
