from __future__ import annotations

import datetime
import sys
from contextlib import contextmanager
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo, available_timezones

import humanize
import pendulum
import pendulum.tz
from pendulum.date import Date as PendulumDate
from pendulum.datetime import DateTime as PendulumDateTime
from pendulum.duration import Duration as PendulumDuration
from pendulum.time import Time as PendulumTime
from pendulum.tz.timezone import Timezone
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


def get_timezones() -> tuple[str, ...]:
    return tuple(available_timezones())


def create_datetime_instance(v: datetime.datetime) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        return v

    return DateTime.instance(v)


def from_timestamp(
    ts: float, tz: str | pendulum.tz.Timezone = UTC
) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        if isinstance(tz, Timezone):
            tz = tz.name
        return datetime.datetime.fromtimestamp(ts, ZoneInfo(tz))

    return pendulum.from_timestamp(ts, tz)


def human_friendly_diff(
    dt: datetime.datetime | None, other: datetime.datetime | None = None
) -> str:
    if dt is None:
        return ""

    # Handle naive datetimes consistently across Python versions
    if dt.tzinfo is None:
        local_tz = datetime.datetime.now().astimezone().tzinfo
        dt = dt.replace(tzinfo=local_tz).astimezone(ZoneInfo("UTC"))
    elif isinstance(dt.tzinfo, Timezone):
        dt = dt.replace(tzinfo=ZoneInfo(dt.tzinfo.name))

    # Handle other parameter if provided
    if other is not None:
        if other.tzinfo is None:
            local_tz = datetime.datetime.now().astimezone().tzinfo
            other = other.replace(tzinfo=local_tz).astimezone(ZoneInfo("UTC"))
        elif isinstance(other.tzinfo, Timezone):
            other = other.replace(tzinfo=ZoneInfo(other.tzinfo.name))

    if sys.version_info >= (3, 13):
        return humanize.naturaltime(dt, when=other)

    return DateTime.instance(dt).diff_for_humans(
        other=DateTime.instance(other) if other else None
    )


def now(
    tz: str | Timezone = "UTC",
) -> DateTime | datetime.datetime:
    if sys.version_info >= (3, 13):
        from whenever import ZonedDateTime

        if isinstance(tz, Timezone):
            tz = tz.name

        return ZonedDateTime.now(tz).py_datetime()
    else:
        return DateTime.now(tz)


def end_of_period(dt: datetime.datetime | DateTime, period: str) -> datetime.datetime:
    """
    Returns the end of the specified unit of time.

    Args:
        dt: The datetime to get the end of.
        period: The period to get the end of.
                Valid values: 'second', 'minute', 'hour', 'day',
                'week'

    Returns:
        DateTime: A new DateTime representing the end of the specified unit.

    Raises:
        ValueError: If an invalid unit is specified.
    """
    if sys.version_info >= (3, 13):
        from whenever import Weekday, ZonedDateTime

        if isinstance(dt, DateTime):
            zdt = ZonedDateTime.from_timestamp(
                dt.timestamp(), tz=dt.tz.name if dt.tz else "UTC"
            )
        else:
            zdt = ZonedDateTime.from_py_datetime(dt)
        if period == "second":
            zdt = zdt.replace(nanosecond=999999999)
        elif period == "minute":
            zdt = zdt.replace(second=59, nanosecond=999999999)
        elif period == "hour":
            zdt = zdt.replace(minute=59, second=59, nanosecond=999999999)
        elif period == "day":
            zdt = zdt.replace(hour=23, minute=59, second=59, nanosecond=999999999)
        elif period == "week":
            days_till_end_of_week: int = (
                Weekday.SUNDAY.value - zdt.date().day_of_week().value
            )
            zdt = zdt.replace(
                day=zdt.day + days_till_end_of_week,
                hour=23,
                minute=59,
                second=59,
                nanosecond=999999999,
            )
        else:
            raise ValueError(f"Invalid period: {period}")

        return zdt.py_datetime()
    else:
        return DateTime.instance(dt).end_of(period)


def start_of_day(dt: datetime.datetime | DateTime) -> datetime.datetime:
    """
    Returns the start of the specified unit of time.

    Args:
        dt: The datetime to get the start of.

    Returns:
        datetime.datetime: A new datetime.datetime representing the start of the specified unit.

    Raises:
        ValueError: If an invalid unit is specified.
    """
    if sys.version_info >= (3, 13):
        from whenever import ZonedDateTime

        if isinstance(dt, DateTime):
            zdt = ZonedDateTime.from_timestamp(
                dt.timestamp(), tz=dt.tz.name if dt.tz else "UTC"
            )
        else:
            zdt = ZonedDateTime.from_py_datetime(dt)

        return zdt.start_of_day().py_datetime()
    else:
        return DateTime.instance(dt).start_of("day")


def earliest_possible_datetime() -> datetime.datetime:
    return datetime.datetime.min.replace(tzinfo=ZoneInfo("UTC"))


@contextmanager
def travel_to(dt: Any):
    if sys.version_info >= (3, 13):
        with mock.patch("prefect.types._datetime.now", return_value=dt):
            yield

    else:
        from pendulum import travel_to

        with travel_to(dt, freeze=True):
            yield


def in_local_tz(dt: datetime.datetime) -> DateTime:
    if sys.version_info >= (3, 13):
        from whenever import LocalDateTime

        return LocalDateTime.from_py_datetime(dt).assume_system_tz()

    return DateTime.instance(dt).in_tz(pendulum.tz.local_timezone())
