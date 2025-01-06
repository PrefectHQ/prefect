from __future__ import annotations

from typing import Annotated, Any

from pendulum import FixedTimezone, format_diff, from_format, instance, parse, tz
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
    return PydanticDateTime(from_format(string, fmt, tz, locale))  # type: ignore


def parse_datetime(string: str) -> DateTime:
    return PydanticDateTime(parse(string))  # type: ignore


def datetime_instance(value: Any) -> DateTime:
    return PydanticDateTime(instance(value))  # type: ignore


def local_timezone() -> Timezone | FixedTimezone:
    return tz.local_timezone()


__all__ = [
    "DateTime",
    "Date",
    "Duration",
    "datetime_from_format",
    "parse_datetime",
    "datetime_instance",
    "format_diff",
]
