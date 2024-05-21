from typing import Annotated, Any, Callable, ClassVar, Type
from typing_extensions import Self

from pydantic import BeforeValidator, Field, GetCoreSchemaHandler
from datetime import timedelta
from zoneinfo import available_timezones
from pydantic_core import core_schema

timezone_set = available_timezones()


NonNegativeInteger = Annotated[int, Field(ge=0)]
PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]

TimeZone = Annotated[str, Field(default="UTC", pattern="|".join(timezone_set))]


class Duration(timedelta):
    schema: ClassVar = core_schema.timedelta_schema(
        ge=timedelta(seconds=0),
        serialization=core_schema.plain_serializer_function_ser_schema(
            timedelta.total_seconds, when_used="json-unless-none"
        ),
    )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return cls.schema


class NonNegativeDuration(Duration):
    """A timedelta that must be greater than or equal to 0."""

    schema: ClassVar = core_schema.timedelta_schema(
        ge=timedelta(seconds=0),
        serialization=core_schema.plain_serializer_function_ser_schema(
            timedelta.total_seconds, when_used="json-unless-none"
        ),
    )


class PositiveDuration(Duration):
    """A timedelta that must be greater than 0."""

    schema: ClassVar = core_schema.timedelta_schema(
        gt=timedelta(seconds=0),
        serialization=core_schema.plain_serializer_function_ser_schema(
            timedelta.total_seconds, when_used="json-unless-none"
        ),
    )


BANNED_CHARACTERS = ["/", "%", "&", ">", "<"]

WITHOUT_BANNED_CHARACTERS = r"^[^" + "".join(BANNED_CHARACTERS) + "]+$"
Name = Annotated[str, Field(pattern=WITHOUT_BANNED_CHARACTERS)]

WITHOUT_BANNED_CHARACTERS_EMPTY_OK = r"^[^" + "".join(BANNED_CHARACTERS) + "]*$"
NameOrEmpty = Annotated[str, Field(pattern=WITHOUT_BANNED_CHARACTERS_EMPTY_OK)]


def non_emptyish(value: str) -> str:
    if isinstance(value, str):
        if not value.strip("' \""):
            raise ValueError("name cannot be an empty string")

    return value


NonEmptyishName = Annotated[
    str,
    Field(pattern=WITHOUT_BANNED_CHARACTERS),
    BeforeValidator(non_emptyish),
]


__all__ = [
    "NonNegativeInteger",
    "PositiveInteger",
    "NonNegativeFloat",
    "NonNegativeDuration",
    "PositiveDuration",
    "Name",
    "NameOrEmpty",
    "NonEmptyishName",
]
