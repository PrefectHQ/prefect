from datetime import timedelta

import pytest
from pydantic import BaseModel, ValidationError

from prefect.types import (
    NonNegativeDuration,
    NonNegativeInteger,
    PositiveDuration,
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


class TestConstrainedDurations:
    @pytest.mark.parametrize(
        "duration_type,valid_value",
        [
            (PositiveDuration, timedelta(seconds=1)),
            (NonNegativeDuration, timedelta(seconds=0)),
        ],
    )
    def test_valid_duration(self, duration_type, valid_value):
        class Model(BaseModel):
            value: duration_type

        m = Model(value=valid_value)
        assert m.value == valid_value

    @pytest.mark.parametrize(
        "duration_type,invalid_value",
        [
            (PositiveDuration, timedelta(seconds=0)),
            (NonNegativeDuration, timedelta(seconds=-1)),
        ],
    )
    def test_invalid_duration(self, duration_type, invalid_value):
        class Model(BaseModel):
            value: duration_type

        with pytest.raises(ValidationError):
            Model(value=invalid_value)
