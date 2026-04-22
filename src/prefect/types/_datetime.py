from __future__ import annotations

import datetime
import sys
from contextlib import contextmanager
from typing import Annotated, Any, Union, cast
from unittest import mock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import humanize
from dateutil.parser import parse
from pydantic import AfterValidator
from typing_extensions import TypeAlias

if sys.version_info >= (3, 13):
    from whenever import DateTimeDelta
    from whenever import ZonedDateTime as _ZDTProbe

    # True on whenever >= 0.10.0, which introduced ZonedDateTime(stdlib_dt),
    # start_of("day"), and to_stdlib(). False on 0.7.x–0.9.x.
    _WHENEVER_NEW_API: bool = hasattr(_ZDTProbe, "to_stdlib")
    del _ZDTProbe

    DateTime: TypeAlias = datetime.datetime
    Date: TypeAlias = datetime.date
    Duration: TypeAlias = datetime.timedelta
    if _WHENEVER_NEW_API:
        from whenever import ItemizedDelta

        Interval: TypeAlias = Union[datetime.timedelta, ItemizedDelta]
    else:
        Interval: TypeAlias = Union[datetime.timedelta, DateTimeDelta]
else:
    _WHENEVER_NEW_API = False
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
    Interval: TypeAlias = datetime.timedelta


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

    def _normalize(ts: datetime.datetime) -> datetime.datetime:
        """Return *ts* with a valid ZoneInfo; fall back to UTC if needed."""
        if ts.tzinfo is None:
            local_tz = datetime.datetime.now().astimezone().tzinfo
            return ts.replace(tzinfo=local_tz).astimezone(ZoneInfo("UTC"))

        if isinstance(ts.tzinfo, ZoneInfo):
            return ts  # already valid

        if tz_name := getattr(ts.tzinfo, "name", None):
            try:
                return ts.replace(tzinfo=ZoneInfo(tz_name))
            except ZoneInfoNotFoundError:
                pass

        return ts.astimezone(ZoneInfo("UTC"))

    dt = _normalize(dt)

    if other is not None:
        other = _normalize(other)

    if sys.version_info >= (3, 13):
        # humanize expects ZoneInfo or None
        return humanize.naturaltime(dt, when=other)

    # Ensure consistency for pendulum path by using UTC
    pendulum_dt = DateTime.instance(dt.astimezone(ZoneInfo("UTC")))
    pendulum_other = (
        DateTime.instance(other.astimezone(ZoneInfo("UTC"))) if other else None
    )
    return pendulum_dt.diff_for_humans(other=pendulum_other)


def _whenever_to_stdlib(obj: Any) -> datetime.datetime:
    """Convert a whenever datetime object to a stdlib datetime.

    Prefers `to_stdlib()` (newer whenever) and falls back to `py_datetime()`
    for older releases that don't yet expose `to_stdlib()`.
    """
    to_stdlib = getattr(obj, "to_stdlib", None)
    if callable(to_stdlib):
        return cast(datetime.datetime, to_stdlib())
    return cast(datetime.datetime, obj.py_datetime())


def _whenever_zdt_from_py(dt: datetime.datetime) -> Any:
    """Create a ZonedDateTime from a stdlib datetime.

    whenever >= 0.10.0 accepts a stdlib datetime directly in the constructor.
    Older versions require the `from_py_datetime()` classmethod.
    """
    from whenever import ZonedDateTime

    if _WHENEVER_NEW_API:
        return ZonedDateTime(dt)  # type: ignore[arg-type]
    return ZonedDateTime.from_py_datetime(dt)


def _whenever_pdt_from_py(dt: datetime.datetime) -> Any:
    """Create a PlainDateTime from a naive stdlib datetime.

    whenever >= 0.10.0 accepts a stdlib datetime directly in the constructor.
    Older versions require the `from_py_datetime()` classmethod.
    """
    from whenever import PlainDateTime

    if _WHENEVER_NEW_API:
        return PlainDateTime(dt)  # type: ignore[arg-type]
    return PlainDateTime.from_py_datetime(dt)


def now(
    tz: str | Any = "UTC",
) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        from whenever import ZonedDateTime

        if isinstance(getattr(tz, "name", None), str):
            tz = tz.name

        return _whenever_to_stdlib(ZonedDateTime.now(tz))
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
        from whenever import Weekday

        if not isinstance(dt.tzinfo, ZoneInfo):
            dt = dt.replace(tzinfo=ZoneInfo(dt.tzname() or "UTC"))
        zdt = _whenever_zdt_from_py(dt)
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
            if _WHENEVER_NEW_API:
                from whenever import ItemizedDateDelta

                zdt = zdt + ItemizedDateDelta(days=days_till_end_of_week)
            else:
                from whenever import days

                zdt = zdt + days(days_till_end_of_week)
            zdt = zdt.replace(
                hour=23,
                minute=59,
                second=59,
                nanosecond=999999999,
            )
        else:
            raise ValueError(f"Invalid period: {period}")

        return _whenever_to_stdlib(zdt)
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
        zdt = _whenever_zdt_from_py(dt)
        zdt = (
            zdt.start_of("day")
            if callable(getattr(zdt, "start_of", None))
            else zdt.start_of_day()
        )

        return _whenever_to_stdlib(zdt)
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
        if dt.tzinfo is None:
            wdt = _whenever_pdt_from_py(dt).assume_system_tz()
        else:
            if not isinstance(dt.tzinfo, ZoneInfo):
                if key := getattr(dt.tzinfo, "key", None):
                    dt = dt.replace(tzinfo=ZoneInfo(key))
                else:
                    utc_dt = dt.astimezone(datetime.timezone.utc)
                    dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))

            wdt = _whenever_zdt_from_py(dt).to_system_tz()

        return _whenever_to_stdlib(wdt)
    else:
        return DateTime.instance(dt).in_tz(pendulum.tz.local_timezone())


def to_datetime_string(dt: datetime.datetime, include_tz: bool = True) -> str:
    if include_tz:
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    else:
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def _validate_positive_interval(v: Interval) -> Interval:
    if isinstance(v, datetime.timedelta):
        if v <= datetime.timedelta(0):
            raise ValueError("interval must be positive")
    elif sys.version_info >= (3, 13):
        if _WHENEVER_NEW_API:
            from whenever import ItemizedDelta

            if isinstance(v, ItemizedDelta) and v.sign() <= 0:
                raise ValueError("interval must be positive")
        elif isinstance(v, DateTimeDelta):
            _months, _days, _secs, _nanos = v.in_months_days_secs_nanos()
            if _months <= 0 and _days <= 0 and _secs <= 0 and _nanos <= 0:
                raise ValueError("interval must be positive")
    return v


PositiveInterval = Annotated[Interval, AfterValidator(_validate_positive_interval)]
