from typing import Annotated, Any, Callable, ClassVar, Generator

from pydantic_core import core_schema, CoreSchema, SchemaValidator
from pydantic import Field
from typing_extensions import Self
from datetime import timedelta


NonNegativeInteger = Annotated[int, Field(ge=0)]


PositiveInteger = Annotated[int, Field(gt=0)]


NonNegativeFloat = Annotated[float, Field(ge=0.0)]


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
