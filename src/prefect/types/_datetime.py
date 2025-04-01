from __future__ import annotations

import datetime
import sys
from contextlib import contextmanager
from typing import Any, cast
from unittest import mock
from zoneinfo import ZoneInfo, available_timezones

import humanize
from dateutil.parser import parse
from typing_extensions import TypeAlias

if sys.version_info >= (3, 13):
    DateTime: TypeAlias = datetime.datetime
    Date: TypeAlias = datetime.date
    Duration: TypeAlias = datetime.timedelta
else:
    import pendulum
    import pendulum.tz
    from pydantic_extra_types.pendulum_dt import (
        Date as PydanticDate,
    )
    from pydantic_extra_types.pendulum_dt import (
        DateTime as PydanticDateTime,
    )
    from pydantic_extra_types.pendulum_dt import (
        Duration as PydanticDuration,
    )

    DateTime: TypeAlias = PydanticDateTime
    Date: TypeAlias = PydanticDate
    Duration: TypeAlias = PydanticDuration


def parse_datetime(dt: str) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        parsed_dt = parse(dt)
        if parsed_dt.tzinfo is None:
            # Assume UTC if no timezone is provided
            return parsed_dt.replace(tzinfo=ZoneInfo("UTC"))
        else:
            return parsed_dt
    else:
        return cast(datetime.datetime, pendulum.parse(dt))


def get_timezones() -> tuple[str, ...]:
    return tuple(available_timezones())


def create_datetime_instance(v: datetime.datetime) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        if v.tzinfo is None:
            # Assume UTC if no timezone is provided
            return v.replace(tzinfo=ZoneInfo("UTC"))
        else:
            return v

    return DateTime.instance(v)


def from_timestamp(ts: float, tz: str | Any = "UTC") -> datetime.datetime:
    if sys.version_info >= (3, 13):
        if not isinstance(tz, str):
            # Handle pendulum edge case
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
    elif hasattr(dt.tzinfo, "name"):
        dt = dt.replace(tzinfo=ZoneInfo(getattr(dt.tzinfo, "name")))

    # Handle other parameter if provided
    if other is not None:
        if other.tzinfo is None:
            local_tz = datetime.datetime.now().astimezone().tzinfo
            other = other.replace(tzinfo=local_tz).astimezone(ZoneInfo("UTC"))
        elif hasattr(other.tzinfo, "name"):
            other = other.replace(tzinfo=ZoneInfo(getattr(other.tzinfo, "name")))

    if sys.version_info >= (3, 13):
        return humanize.naturaltime(dt, when=other)

    return DateTime.instance(dt).diff_for_humans(
        other=DateTime.instance(other) if other else None
    )


def now(
    tz: str | Any = "UTC",
) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        from whenever import ZonedDateTime

        if isinstance(getattr(tz, "name", None), str):
            tz = tz.name

        return ZonedDateTime.now(tz).py_datetime()
    else:
        return pendulum.now(tz)


def end_of_period(dt: datetime.datetime, period: str) -> datetime.datetime:
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
        from whenever import Weekday, ZonedDateTime, days

        if not isinstance(dt.tzinfo, ZoneInfo):
            zdt = ZonedDateTime.from_py_datetime(
                dt.replace(tzinfo=ZoneInfo(dt.tzname() or "UTC"))
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
            zdt = zdt + days(days_till_end_of_week)
            zdt = zdt.replace(
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

        if hasattr(dt, "tz"):
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


def in_local_tz(dt: datetime.datetime) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        from whenever import LocalDateTime, ZonedDateTime

        if dt.tzinfo is None:
            wdt = LocalDateTime.from_py_datetime(dt)
        else:
            if not isinstance(dt.tzinfo, ZoneInfo):
                if key := getattr(dt.tzinfo, "key", None):
                    dt = dt.replace(tzinfo=ZoneInfo(key))
                else:
                    utc_dt = dt.astimezone(datetime.timezone.utc)
                    dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))

            wdt = ZonedDateTime.from_py_datetime(dt).to_system_tz()

        return wdt.py_datetime()

    return DateTime.instance(dt).in_tz(pendulum.tz.local_timezone())


def to_datetime_string(dt: datetime.datetime, include_tz: bool = True) -> str:
    if include_tz:
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    else:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
