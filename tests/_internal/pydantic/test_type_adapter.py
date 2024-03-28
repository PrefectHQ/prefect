from typing import Any, List, Type, TypeVar, Union

import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import validate_python
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS

T = TypeVar("T")


class Model(BaseModel):
    a: int
    b: str
    c: bool


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when compatibility is enabled or v1 is installed",
)
@pytest.mark.parametrize(
    "type_, value, expected",
    [
        (int, 42, 42),
        (str, "42", "42"),
        (bool, True, True),
        (Model, {"a": 42, "b": "42", "c": True}, Model(a=42, b="42", c=True)),
        (List[Model], [{"a": 42, "b": "42", "c": True}], [Model(a=42, b="42", c=True)]),
    ],
)
def test_validate_python(type_: Union[T, Type[T]], value: Any, expected: Any) -> None:
    """with either:
        - v2 installed and compatibility layer enabled
        - or v1 installed

    everything should work without deprecation warnings
    """
    assert validate_python(type_, value) == expected


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="These tests are only valid when compatibility is disabled and v2 is installed",
)
@pytest.mark.parametrize(
    "type_, value, expected",
    [
        (int, 42, 42),
        (str, "42", "42"),
        (bool, True, True),
        (Model, {"a": 42, "b": "42", "c": True}, Model(a=42, b="42", c=True)),
        (List[Model], [{"a": 42, "b": "42", "c": True}], [Model(a=42, b="42", c=True)]),
    ],
)
def test_validate_python_with_deprecation_warnings(
    type_: Type[T], value: Any, expected: Any
) -> None:
    """with v2 installed and compatibility layer disabled, we should see deprecation warnings"""
    from pydantic import PydanticDeprecatedSince20

    with pytest.warns(PydanticDeprecatedSince20):
        assert validate_python(type_, value) == expected
