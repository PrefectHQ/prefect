from typing import Any, Dict

import pytest
from pydantic import BaseModel

from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS
from prefect._internal.pydantic._validators import model_validator


def bigger_than_ten(data: Dict[str, Any]) -> Dict[str, Any]:
    a = data.get("a")
    if not isinstance(a, int):
        raise ValueError("Value must be an integer")
    if a <= 10:
        raise ValueError("Value must be bigger than 10")
    return data


def prepend_with_hello(data: Dict[str, Any]) -> Dict[str, Any]:
    print(data)
    value = data.pop("b")
    if not isinstance(value, str):
        raise ValueError("Value must be a string")
    data["b"] = f"Hello {value}"
    print(data)
    return data


def check_has_hello(data: Dict[str, Any]) -> Dict[str, Any]:
    value = data.get("b")
    if not isinstance(value, str):
        raise ValueError("Value must be a string")
    if "Hello" != value[:5]:
        raise ValueError("Value must start with 'Hello'")
    return data


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when pydantic compatibility layer is enabled or when v1 is installed",
)
def test_model_validator():
    """
    with either:
        - v2 installed and compatibility layer enabled
        - or v1 installed

    everything should work without deprecation warnings
    """
    from pydantic.error_wrappers import ValidationError

    class TestModel(BaseModel):
        a: int
        b: str

        @model_validator(mode="before")
        @classmethod
        def validate_a(cls, v: Any) -> Any:
            return bigger_than_ten(v)

        @model_validator(mode="before")
        @classmethod
        def prepend_hello(cls, v: Any) -> Any:
            return prepend_with_hello(v)

        # @model_validator(mode="after")
        # def check_hello(cls, v: Any) -> Any:
        #     return check_has_hello(v)

    with pytest.raises(ValidationError):
        model = TestModel(a=1, b="2")
    model = TestModel(a=11, b="2")
    assert model.b == "Hello 2"
    assert model.a == 11  # Original model should remain unchanged


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when compatibility layer is disabled and v2 is installed",
)
def test_model_validator_with_flag_disabled():
    """
    with v2 installed and compatibility layer disabled, we should see deprecation warnings
    """
    from pydantic import ValidationError

    class TestModel(BaseModel):
        a: int
        b: str

        @model_validator(mode="before")
        @classmethod
        def validate_a(cls, v: Any) -> Any:
            return bigger_than_ten(v)

        @model_validator(mode="before")
        @classmethod
        def prepend_hello(cls, v: Any) -> Any:
            return prepend_with_hello(v)

        # @model_validator(mode="after")
        # def check_hello(cls, v: Any) -> Any:
        #     return check_has_hello(v)

    with pytest.raises(ValidationError):
        model = TestModel(a=1, b="2")
    model = TestModel(a=11, b="2")
    assert model.b == "Hello 2"
    assert model.a == 11  # Original model should remain unchanged
