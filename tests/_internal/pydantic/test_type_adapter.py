from typing import List

import pytest
from pydantic import BaseModel

from prefect._internal.pydantic import validate_python
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
    c: bool


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

    # check it works with the flag disabled
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS: False}):
        # parse_obj_as doesn't handle the `Model` / `List[Model]` case out of the box
        if isinstance(expected, BaseModel) or (
            isinstance(expected, list)
            and all(isinstance(i, BaseModel) for i in expected)
        ):
            with pytest.raises(RuntimeError, match="no validator found for"):
                assert validate_python(type_, value) == expected
        else:
            assert validate_python(type_, value) == expected
