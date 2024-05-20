from typing import Annotated

from pydantic import Field
from datetime import timedelta


NonNegativeInteger = Annotated[int, Field(ge=0)]


PositiveInteger = Annotated[int, Field(gt=0)]


NonNegativeFloat = Annotated[float, Field(ge=0.0)]


NonNegativeDuration = Annotated[timedelta, Field(ge=0)]

PositiveDuration = Annotated[timedelta, Field(gt=0)]

__all__ = [
    "NonNegativeInteger",
    "PositiveInteger",
    "NonNegativeFloat",
    "NonNegativeDuration",
    "PositiveDuration",
]
