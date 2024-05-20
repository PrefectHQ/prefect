from typing import Annotated, Any, Callable, ClassVar

from pydantic_core import core_schema, CoreSchema
from pydantic import Field
from datetime import timedelta
import zoneinfo

timezones = zoneinfo.available_timezones()

NonNegativeInteger = Annotated[int, Field(ge=0)]

PositiveInteger = Annotated[int, Field(gt=0)]

NonNegativeFloat = Annotated[float, Field(ge=0.0)]


class TimeZone(str):
    schema = core_schema.with_default_schema(
        schema=core_schema.str_schema(pattern="|".join(timezones)),
        default="UTC",
    )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema


class NonNegativeDuration(timedelta):
    """A timedelta that must be greater than or equal to 0."""

    schema: ClassVar = core_schema.timedelta_schema(ge=timedelta(seconds=0))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema


class PositiveDuration(timedelta):
    """A timedelta that must be greater than 0."""

    schema: ClassVar = core_schema.timedelta_schema(gt=timedelta(seconds=0))

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: Callable[..., Any]
    ) -> CoreSchema:
        return cls.schema


__all__ = [
    "NonNegativeInteger",
    "PositiveInteger",
    "NonNegativeFloat",
    "NonNegativeDuration",
    "PositiveDuration",
]
