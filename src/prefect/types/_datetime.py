from __future__ import annotations

from typing import Annotated, Any

from pendulum import (
    FixedTimezone,
    format_diff,
    parse,
    tz,
)
from pendulum import (
    from_format as from_format_pendulum,
)
from pendulum import (
    from_timestamp as from_timestamp_pendulum,
)
from pendulum import (
    instance as instance_pendulum,
)
from pendulum.tz import UTC, Timezone
from pydantic import Field
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


def from_format(
    string: str,
    fmt: str,
    tz: str | Timezone = UTC,
    locale: str | None = None,
) -> DateTime:
    return from_format_pendulum(string, fmt, tz, locale)  # type: ignore


def parse_datetime(string: str) -> DateTime:
    return parse(string)  # type: ignore


def datetime_instance(value: Any) -> DateTime:
    """
    Here to fulfull the needs that pendulum.instance meets, but it
    is often used ambiguously and we should phase this out over time
    in favor of more explicit datetime utilities.
    """
    return instance_pendulum(value)  # type: ignore


def local_timezone() -> Timezone | FixedTimezone:
    return tz.local_timezone()


def from_timestamp(timestamp: float) -> DateTime:
    return from_timestamp_pendulum(timestamp)  # type: ignore


__all__ = [
    "DateTime",
    "Date",
    "Duration",
    "from_format",
    "parse_datetime",
    "datetime_instance",
    "format_diff",
]
