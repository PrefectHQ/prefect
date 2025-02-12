from __future__ import annotations

import datetime
from typing import Any

import pendulum
import pendulum.tz
from pendulum.date import Date as PendulumDate
from pendulum.datetime import DateTime as PendulumDateTime
from pendulum.duration import Duration as PendulumDuration
from pendulum.time import Time as PendulumTime
from pendulum.tz.timezone import FixedTimezone, Timezone
from pydantic_extra_types.pendulum_dt import (
    Date as PydanticDate,
)
from pydantic_extra_types.pendulum_dt import (
    DateTime as PydanticDateTime,
)
from pydantic_extra_types.pendulum_dt import (
    Duration as PydanticDuration,
)
from typing_extensions import TypeAlias

DateTime: TypeAlias = PydanticDateTime
Date: TypeAlias = PydanticDate
Duration: TypeAlias = PydanticDuration
UTC: pendulum.tz.Timezone = pendulum.tz.UTC


def parse_datetime(
    value: str,
    **options: Any,
) -> PendulumDateTime | PendulumDate | PendulumTime | PendulumDuration:
    return pendulum.parse(value, **options)


def format_diff(
    diff: PendulumDuration,
    is_now: bool = True,
    absolute: bool = False,
    locale: str | None = None,
) -> str:
    return pendulum.format_diff(diff, is_now, absolute, locale)


def local_timezone() -> Timezone | FixedTimezone:
    return pendulum.tz.local_timezone()


def get_timezones() -> tuple[str, ...]:
    return pendulum.tz.timezones()


def create_datetime_instance(v: datetime.datetime) -> DateTime:
    return DateTime.instance(v)


def from_format(
    value: str,
    fmt: str,
    tz: str | Timezone = UTC,
    locale: str | None = None,
) -> DateTime:
    return DateTime.instance(pendulum.from_format(value, fmt, tz, locale))


def from_timestamp(ts: float, tz: str | pendulum.tz.Timezone = UTC) -> DateTime:
    return DateTime.instance(pendulum.from_timestamp(ts, tz))


def human_friendly_diff(dt: DateTime | datetime.datetime) -> str:
    if isinstance(dt, DateTime):
        return dt.diff_for_humans()
    else:
        return DateTime.instance(dt).diff_for_humans()


def now(tz: str | Timezone = UTC) -> DateTime:
    return DateTime.now(tz)


def add_years(dt: DateTime, years: int) -> DateTime:
    return dt.add(years=years)


def end_of_period(dt: DateTime, period: str) -> DateTime:
    """
    Returns the end of the specified unit of time.

    Args:
        dt: The datetime to get the end of.
        period: The period to get the end of.
                Valid values: 'second', 'minute', 'hour', 'day',
                'week', 'month', 'quarter', 'year'

    Returns:
        DateTime: A new DateTime representing the end of the specified unit.

    Raises:
        ValueError: If an invalid unit is specified.
    """
    return dt.end_of(period)


def start_of_period(dt: DateTime, period: str) -> DateTime:
    """
    Returns the start of the specified unit of time.

    Args:
        dt: The datetime to get the start of.
        period: The period to get the start of.
                Valid values: 'second', 'minute', 'hour', 'day',
                'week', 'month', 'quarter', 'year'

    Returns:
        DateTime: A new DateTime representing the start of the specified unit.

    Raises:
        ValueError: If an invalid unit is specified.
    """
    return dt.start_of(period)


def earliest_possible_datetime() -> DateTime:
    return DateTime.instance(datetime.datetime.min)
