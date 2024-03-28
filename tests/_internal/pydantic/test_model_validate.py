from typing import cast

import pytest
from pydantic import BaseModel, ValidationError

from prefect._internal.pydantic._compat import model_validate
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


class Model(BaseModel):
    a: int
    b: str


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="Valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_validate():
    """
    with either:
        - v2 installed and compatibility layer enabled
        - or v1 installed

    everything should work without deprecation warnings
    """
    model_instance = model_validate(Model, {"a": 1, "b": "test"})

    assert isinstance(model_instance, Model)

    assert cast(Model, model_instance).a == 1  # type: ignore

    assert cast(Model, model_instance).b == "test"  # type: ignore


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="Only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_validate_with_flag_disabled():
    """with v2 installed and compatibility layer disabled, we should see deprecation warnings"""
    from pydantic import PydanticDeprecatedSince20

    with pytest.warns(PydanticDeprecatedSince20):
        model_instance = model_validate(Model, {"a": 1, "b": "test"})

    assert cast(Model, model_instance).a == 1  # type: ignore

    assert cast(Model, model_instance).b == "test"  # type: ignore


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_validate_with_invalid_model():
    """
    with either:
        - v2 installed and compatibility layer enabled
        - or v1 installed

    everything should work without deprecation warnings
    """
    try:
        model_validate(Model, {"a": "not an int", "b": "test"})
    except ValidationError as e:
        errors = e.errors()

        assert len(errors) == 1

        error = errors[0]

        assert error["loc"] == ("a",)
        assert "valid integer" in error["msg"]


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_validate_with_invalid_model_and_flag_disabled():
    """with v2 installed and compatibility layer disabled, we should see deprecation warnings"""
    from pydantic import PydanticDeprecatedSince20

    with pytest.warns(PydanticDeprecatedSince20):
        try:
            model_validate(Model, {"a": "not an int", "b": "test"})
        except ValidationError as e:
            errors = e.errors()

            assert len(errors) == 1

            error = errors[0]

            assert error["loc"] == ("a",)
            assert "valid integer" in error["msg"]
