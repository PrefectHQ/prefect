import pytest
from pydantic import BaseModel, ValidationError

from prefect._internal.pydantic._compat import HAS_PYDANTIC_V2, model_validate
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS,
    temporary_settings,
)


@pytest.fixture(autouse=True)
def enable_v2_internals():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: True}):
        yield


class Model(BaseModel):
    a: int
    b: str


def test_model_validate(caplog):
    model_instance = model_validate(Model, {"a": 1, "b": "test"})

    assert model_instance.a == 1

    assert model_instance.b == "test"

    if HAS_PYDANTIC_V2:
        assert (
            "Using Pydantic v2 compatibility layer for `model_validate`" in caplog.text
        )

    else:
        assert "Pydantic v2 is not installed." in caplog.text


def test_model_validate_with_flag_disabled(caplog):
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: False}):
        if HAS_PYDANTIC_V2:
            from pydantic.warnings import PydanticDeprecatedSince20

            with pytest.warns(PydanticDeprecatedSince20):
                model_instance = model_validate(Model, {"a": 1, "b": "test"})
        else:
            model_instance = model_validate(Model, {"a": 1, "b": "test"})

    assert model_instance.a == 1

    assert model_instance.b == "test"

    if HAS_PYDANTIC_V2:
        assert "Pydantic v2 compatibility layer is disabled" in caplog.text
    else:
        assert "Pydantic v2 is not installed." in caplog.text


def test_model_validate_with_invalid_model(caplog):
    try:
        model_validate(Model, {"a": "not an int", "b": "test"})
    except ValidationError as e:
        errors = e.errors()

        assert len(errors) == 1

        error = errors[0]

        assert error["loc"] == ("a",)
        assert "valid integer" in error["msg"]
