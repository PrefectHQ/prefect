import pytest
from pydantic import BaseModel, ValidationError

from prefect.types import (
    NonNegativeInteger,
    PositiveInteger,
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
