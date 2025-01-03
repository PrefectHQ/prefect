from typing import Annotated

from pendulum import from_format
from pendulum.tz import UTC, Timezone
from pydantic import (
    Field,
)
from pydantic_extra_types.pendulum_dt import Date as PydanticDate
from pydantic_extra_types.pendulum_dt import DateTime as PydanticDateTime
from pydantic_extra_types.pendulum_dt import Duration as PydanticDuration
from typing_extensions import TypeAlias
from zoneinfo import available_timezones

TimeZone = Annotated[
    str,
    Field(
        default="UTC",
        pattern="|".join(
            [z for z in sorted(available_timezones()) if "localtime" not in z]
        ),
    ),
]

DateTime: TypeAlias = PydanticDateTime
Date: TypeAlias = PydanticDate
Duration: TypeAlias = PydanticDuration


def datetime_from_format(
    string: str,
    fmt: str,
    tz: str | Timezone = UTC,
    locale: str | None = None,
) -> DateTime:
    return PydanticDateTime(from_format(string, fmt, tz, locale))
