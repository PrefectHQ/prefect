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
    @pytest.mark.parametrize("integer_type", [PositiveInteger, NonNegativeInteger])
    @pytest.mark.parametrize("value", [0, 1, 2, 3])
    def test_valid_integer(self, integer_type, value):
        class Model(BaseModel):
            value: integer_type

        if integer_type == PositiveInteger and value == 0:
            with pytest.raises(ValidationError):
                Model(value=value)
        else:
            m = Model(value=value)
            assert m.value == value

    @pytest.mark.parametrize("integer_type", [PositiveInteger, NonNegativeInteger])
    @pytest.mark.parametrize("value", [-1, -2, -3])
    def test_invalid_negative_integer(self, integer_type, value):
        class Model(BaseModel):
            value: integer_type

        with pytest.raises(ValidationError):
            Model(value=value)


class TestConstrainedDurations:
    @pytest.mark.parametrize("duration_type", [PositiveDuration, NonNegativeDuration])
    @pytest.mark.parametrize("value", [0, 1, 2, 3])
    def test_valid_duration(self, duration_type, value):
        class Model(BaseModel):
            value: duration_type

        if duration_type == PositiveDuration and value == 0:
            with pytest.raises(ValidationError):
                Model(value=value)
        else:
            m = Model(value=value)
            assert m.value == timedelta(seconds=value)

    @pytest.mark.parametrize("duration_type", [PositiveDuration, NonNegativeDuration])
    @pytest.mark.parametrize("value", [-1, -2, -3])
    def test_invalid_negative_duration(self, duration_type, value):
        class Model(BaseModel):
            value: duration_type

        with pytest.raises(ValidationError):
            Model(value=value)
