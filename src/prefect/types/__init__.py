from typing import Annotated

from pydantic import Field
from datetime import timedelta
from zoneinfo import available_timezones

timezone_set = available_timezones()


NonNegativeInteger = Annotated[int, Field(ge=0)]


PositiveInteger = Annotated[int, Field(gt=0)]


NonNegativeFloat = Annotated[float, Field(ge=0.0)]


NonNegativeDuration = Annotated[timedelta, Field(ge=0)]

PositiveDuration = Annotated[timedelta, Field(gt=0)]

TimeZone = Annotated[str, Field(default="UTC", pattern="|".join(timezone_set))]

__all__ = [
    "NonNegativeInteger",
    "PositiveInteger",
    "NonNegativeFloat",
    "NonNegativeDuration",
    "PositiveDuration",
]
