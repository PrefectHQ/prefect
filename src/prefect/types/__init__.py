from typing import Annotated

from pydantic import BeforeValidator, Field
from datetime import timedelta
from zoneinfo import available_timezones

timezone_set = available_timezones()


NonNegativeInteger = Annotated[int, Field(ge=0)]
PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]

NonNegativeDuration = Annotated[timedelta, Field(ge=timedelta(seconds=0))]
PositiveDuration = Annotated[timedelta, Field(gt=timedelta(seconds=0))]
TimeZone = Annotated[str, Field(default="UTC", pattern="|".join(timezone_set))]


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
