from typing import List

import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import validate_python
from prefect._internal.pydantic._flags import EXPECT_DEPRECATION_WARNINGS


class Model(BaseModel):
    a: int
    b: str
    c: bool


@pytest.mark.skipif(
    EXPECT_DEPRECATION_WARNINGS,
    reason="Valid when compatibility is enabled or v1 is installed",
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
def test_validate_python(type_, value, expected):
    assert validate_python(type_, value) == expected


@pytest.mark.skipif(
    not EXPECT_DEPRECATION_WARNINGS,
    reason="Valid when compatibility is disabled and v2 is installed",
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
def test_validate_python_with_deprecation_warnings(type_, value, expected):
    from pydantic import PydanticDeprecatedSince20

    with pytest.warns(PydanticDeprecatedSince20):
        assert validate_python(type_, value) == expected
