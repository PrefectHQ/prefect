from functools import partial
from typing import Annotated, List

import pytest
from pydantic import BaseModel, BeforeValidator, TypeAdapter, ValidationError

from prefect.types import (
    NonNegativeInteger,
    PositiveInteger,
    validate_list_T_from_delim_string,
)


class TestConstrainedIntegers:
    @pytest.mark.parametrize(
        "integer_type,valid_value",
        [
            (PositiveInteger, 1),
            (NonNegativeInteger, 0),
        ],
    )
    def test_valid_integer(self, integer_type, valid_value):
        class Model(BaseModel):
            value: integer_type

        m = Model(value=valid_value)
        assert m.value == valid_value

    @pytest.mark.parametrize(
        "integer_type,invalid_value",
        [
            (PositiveInteger, 0),
            (NonNegativeInteger, -1),
        ],
    )
    def test_invalid_integer(self, integer_type, invalid_value):
        class Model(BaseModel):
            value: integer_type

        with pytest.raises(ValidationError):
            Model(value=invalid_value)


class TestCustomValidationLogic:
    @pytest.mark.parametrize(
        "value,delim,expected",
        [
            (None, None, []),
            ("", None, []),
            ("429", None, [429]),
            ("404,429,503", None, [404, 429, 503]),
            ("401|403|409", "|", [401, 403, 409]),
            (419, None, [419]),
            ([307, 404, 429, 503], None, [307, 404, 429, 503]),
        ],
        ids=[
            "None",
            "empty string",
            "single int as string",
            "comma separated ints as string",
            "pipe separated ints as string",
            "single int",
            "multiple ints in list",
        ],
    )
    def test_valid_list_of_ints(self, value, delim, expected):
        """e.g. scooping PREFECT_CLIENT_RETRY_EXTRA_CODES"""
        scoop_list_int_from_string = BeforeValidator(
            partial(validate_list_T_from_delim_string, type_=int, delim=delim)
        )
        _type = Annotated[List[int], scoop_list_int_from_string]
        assert TypeAdapter(_type).validate_python(value) == expected

    def test_invalid_list_of_ints(self):
        scoop_list_int_from_string = BeforeValidator(
            partial(validate_list_T_from_delim_string, type_=int)
        )
        _type = Annotated[List[int], scoop_list_int_from_string]
        with pytest.raises(ValidationError, match="should be a valid int"):
            TypeAdapter(_type).validate_python("just,trust,me")
