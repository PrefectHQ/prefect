from typing import Annotated, Any, ClassVar, Dict, List, Type, Union
import orjson
import pydantic

from pydantic import (
    BeforeValidator,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
)
from datetime import timedelta
from zoneinfo import available_timezones
from pydantic_core import core_schema

MAX_VARIABLE_NAME_LENGTH = 255
MAX_VARIABLE_VALUE_LENGTH = 5000

timezone_set = available_timezones()

NonNegativeInteger = Annotated[int, Field(ge=0)]
PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
TimeZone = Annotated[str, Field(default="UTC", pattern="|".join(timezone_set))]


class Duration(timedelta):
    schema: ClassVar = core_schema.timedelta_schema(
        serialization=core_schema.plain_serializer_function_ser_schema(
            timedelta.total_seconds, when_used="json-unless-none"
        ),
    )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Type[Any], handler: Any
    ) -> core_schema.CoreSchema:
        # Allows us to parse numeric and string representations of durations
        def parse_duration(value: Any) -> timedelta:
            if isinstance(value, (float, int)):
                return timedelta(seconds=value)
            elif isinstance(value, str):
                try:
                    return timedelta(seconds=float(value))
                except ValueError:
                    return value  # type: ignore
            return value

        return core_schema.no_info_before_validator_function(parse_duration, cls.schema)


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
    if not value.strip("' \""):
        raise ValueError("name cannot be an empty string")

    return value


NonEmptyishName = Annotated[
    str,
    Field(pattern=WITHOUT_BANNED_CHARACTERS),
    BeforeValidator(non_emptyish),
]


VariableValue = Union[
    StrictStr,
    StrictInt,
    StrictFloat,
    StrictBool,
    None,
    Dict[str, Any],
    List[Any],
]


def check_variable_value(value: object) -> object:
    try:
        json_string = orjson.dumps(value)
    except orjson.JSONEncodeError:
        raise ValueError("Variable value must be serializable to JSON")

    if value is not None and len(json_string) > MAX_VARIABLE_VALUE_LENGTH:
        raise ValueError(
            f"Variable value must be less than {MAX_VARIABLE_VALUE_LENGTH} characters"
        )
    return value


StrictVariableValue = Annotated[VariableValue, BeforeValidator(check_variable_value)]


class SecretDict(pydantic.Secret[Dict[str, Any]]):
    pass


__all__ = [
    "NonNegativeInteger",
    "PositiveInteger",
    "NonNegativeFloat",
    "NonNegativeDuration",
    "PositiveDuration",
    "Name",
    "NameOrEmpty",
    "NonEmptyishName",
    "SecretDict",
]
