from __future__ import annotations

import datetime
import sys
import warnings
from contextlib import contextmanager, nullcontext
from typing import TYPE_CHECKING, Annotated, Any, TypeAlias, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import humanize
from dateutil.parser import parse
from pydantic import AfterValidator, GetCoreSchemaHandler, WithJsonSchema
from pydantic_core import core_schema as _core_schema
from whenever import (
    DateTimeDelta,
    Instant,
    PlainDateTime,
    Weekday,
    ZonedDateTime,
    patch_current_time,
)
from whenever import ZonedDateTime as _ZDTProbe

# True on whenever >= 0.10.0, which introduced ZonedDateTime(stdlib_dt),
# start_of("day"), and to_stdlib(). False on 0.7.x–0.9.x.
_WHENEVER_NEW_API: bool = hasattr(_ZDTProbe, "to_stdlib")
del _ZDTProbe


class _DateTime(datetime.datetime):
    """`datetime.datetime` with a Pydantic schema that coerces naive to UTC.

    Any field typed as `DateTime` gets a tz-awareness guarantee instead of
    deferring to ad-hoc per-field validators (see #21949). Coercion reuses
    the existing `create_datetime_instance` helper rather than open-coding
    the naive→UTC check.

    Runtime construction (`DateTime(2020, 1, 1)`) preserves the underlying
    `datetime.datetime` semantics — naive in, naive out. The coercion
    applies during Pydantic validation, which is where the silent
    server-side drop originated.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> _core_schema.CoreSchema:
        return _core_schema.no_info_after_validator_function(
            create_datetime_instance,
            handler(datetime.datetime),
        )


if sys.version_info >= (3, 13):
    DateTime: TypeAlias = _DateTime
    Date: TypeAlias = datetime.date
    Duration: TypeAlias = datetime.timedelta
else:
    import pendulum
    from pydantic_extra_types.pendulum_dt import Date as PydanticDate
    from pydantic_extra_types.pendulum_dt import DateTime as PydanticDateTime
    from pydantic_extra_types.pendulum_dt import Duration as PydanticDuration

    DateTime: TypeAlias = PydanticDateTime
    Date: TypeAlias = PydanticDate
    Duration: TypeAlias = PydanticDuration

    warnings.warn(
        "Pendulum datetime behavior on Python 3.11 and 3.12 is deprecated. "
        "It will be retained for at least six months and three minor version "
        "increases after the deprecation release, whichever is longer. "
        "A later minor release will return standard-library datetime types. "
        "See https://docs.prefect.io/v3/get-started/install#datetime-values "
        "for migration guidance.",
        DeprecationWarning,
        stacklevel=2,
    )

if TYPE_CHECKING or _WHENEVER_NEW_API:
    from whenever import ItemizedDelta
else:
    from whenever import DateTimeDelta as ItemizedDelta

# Pydantic also accepts repeated ISO units and a fraction on the final unit.
_TIMEDELTA_ISO_PATTERN = (
    r"P(?=[0-9]|T[0-9])(?:[0-9]+[YMWD])*"
    r"(?:[0-9]+[.,][0-9]*[YMWD]T?|T(?:[0-9]+[HMS])*(?:[0-9]+[.,][0-9]*[HMS])?)?"
)
_ITEMIZED_ISO_PATTERN = (
    r"[Pp](?=[0-9]|[Tt][0-9])(?:[0-9]+[Yy])?(?:[0-9]+[Mm])?"
    r"(?:[0-9]+[Ww])?(?:[0-9]+[Dd])?(?:[Tt](?:[0-9]+[Hh])?"
    r"(?:[0-9]+[Mm])?(?:[0-9]+(?:[.,][0-9]{1,9})?[Ss])?)?"
)
_INTERVAL_CLOCK_PATTERN = (
    r"(?:[0-9]{2,10}:[0-5][0-9]|"
    r"[0-9]{0,10}:[0-5][0-9]:[0-5][0-9](?:[.,][0-9]+)?)"
)
_INTERVAL_DAYS_PATTERN = r"[0-9]+ ?[dD](?:ays?|AYS?)?(?:, ?| )?"

Interval: TypeAlias = Annotated[
    datetime.timedelta | ItemizedDelta,
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number"},
                {
                    "type": "string",
                    # The end assertion also rejects a trailing newline in JS/Python.
                    "pattern": (
                        rf"^[+-]?(?:{_TIMEDELTA_ISO_PATTERN}|{_ITEMIZED_ISO_PATTERN}|"
                        rf"{_INTERVAL_CLOCK_PATTERN}|{_INTERVAL_DAYS_PATTERN}"
                        rf"(?:(?=0*(?:[0-9]|1[0-9]|2[0-3])?:)"
                        rf"{_INTERVAL_CLOCK_PATTERN})?)(?![\s\S])"
                    ),
                },
            ]
        },
    ),
]


def parse_datetime(dt: str) -> datetime.datetime:
    if sys.version_info < (3, 13):
        return cast(datetime.datetime, pendulum.parse(dt))
    parsed_dt = parse(dt)
    if parsed_dt.tzinfo is None:
        # Assume UTC if no timezone is provided
        return parsed_dt.replace(tzinfo=ZoneInfo("UTC"))
    else:
        return parsed_dt


def get_timezones() -> tuple[str, ...]:
    return tuple(available_timezones())


def create_datetime_instance(v: datetime.datetime) -> datetime.datetime:
    if sys.version_info < (3, 13):
        return DateTime.instance(v)
    if v.tzinfo is None:
        # Assume UTC if no timezone is provided
        return v.replace(tzinfo=ZoneInfo("UTC"))
    else:
        return v


def from_timestamp(ts: float, tz: str | Any = "UTC") -> datetime.datetime:
    if sys.version_info < (3, 13):
        return pendulum.from_timestamp(ts, tz)
    tz = _tzinfo_for_conversion(tz)
    if isinstance(tz, str):
        tz = ZoneInfo(tz)
    return datetime.datetime.fromtimestamp(ts, tz)


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

    if sys.version_info < (3, 13):
        pendulum_dt = DateTime.instance(dt.astimezone(ZoneInfo("UTC")))
        pendulum_other = (
            DateTime.instance(other.astimezone(ZoneInfo("UTC"))) if other else None
        )
        return pendulum_dt.diff_for_humans(other=pendulum_other)

    # humanize expects ZoneInfo or None
    return humanize.naturaltime(dt, when=other)


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
    if isinstance(dt.tzinfo, ZoneInfo) and type(dt.tzinfo) is not ZoneInfo:
        # Whenever requires an exact ZoneInfo, not Pendulum's subclass.
        dt = datetime.datetime.combine(dt, dt.timetz()).replace(
            tzinfo=ZoneInfo(dt.tzinfo.key)
        )
    if _WHENEVER_NEW_API:
        return ZonedDateTime(dt)  # type: ignore[arg-type]
    return ZonedDateTime.from_py_datetime(dt)


def _whenever_pdt_from_py(dt: datetime.datetime) -> Any:
    """Create a PlainDateTime from a naive stdlib datetime.

    whenever >= 0.10.0 accepts a stdlib datetime directly in the constructor.
    Older versions require the `from_py_datetime()` classmethod.
    """
    if _WHENEVER_NEW_API:
        return PlainDateTime(dt)  # type: ignore[arg-type]
    return PlainDateTime.from_py_datetime(dt)


def _tzinfo_for_conversion(tz: Any) -> str | datetime.tzinfo:
    """Normalize a `tz` argument to an IANA name or a stdlib `tzinfo`.

    whenever only accepts IANA names, so `ZoneInfo` and pendulum-style
    objects are unwrapped to their `.key`/`.name`; fixed-offset and other
    `tzinfo` implementations are returned as-is for the caller to handle
    with stdlib arithmetic.
    """
    if isinstance(tz, str):
        return tz
    if isinstance(tz, ZoneInfo):
        return tz.key
    name = getattr(tz, "name", None)
    if isinstance(name, str):
        if isinstance(tz, datetime.tzinfo):
            try:
                ZoneInfo(name)
            except ZoneInfoNotFoundError:
                # Fixed-offset names such as "+05:30" are not IANA keys.
                return tz
        return name
    key = getattr(tz, "key", None)
    if isinstance(key, str):
        return key
    return tz


def _zdt_or_fixed_offset(dt: datetime.datetime) -> datetime.datetime:
    """Return a datetime whose tzinfo is `ZoneInfo` whenever possible.

    whenever requires IANA zones. Aware datetimes carrying a `ZoneInfo`-like
    or named tzinfo are rekeyed; fixed-offset datetimes (e.g. from parsed
    timestamps) cannot be represented as `ZonedDateTime` and are returned
    unchanged for the naive-frame path.
    """
    if dt.tzinfo is None or isinstance(dt.tzinfo, ZoneInfo):
        return dt
    key = _tzinfo_for_conversion(dt.tzinfo)
    if isinstance(key, str):
        try:
            return dt.replace(tzinfo=ZoneInfo(key))
        except ZoneInfoNotFoundError:
            pass
    return dt


def now(
    tz: str | Any = "UTC",
) -> datetime.datetime:
    if sys.version_info < (3, 13):
        return pendulum.now(tz)
    tz = _tzinfo_for_conversion(tz)
    zdt_now = ZonedDateTime.now(tz if isinstance(tz, str) else "UTC")
    now_dt = _whenever_to_stdlib(zdt_now)
    if not isinstance(tz, str):
        now_dt = now_dt.astimezone(tz)
    return now_dt


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
    if sys.version_info < (3, 13):
        return DateTime.instance(dt).end_of(period)
    dt = _zdt_or_fixed_offset(dt)
    if dt.tzinfo is not None and not isinstance(dt.tzinfo, ZoneInfo):
        # Fixed-offset and other non-IANA tzinfo: compute the wall-clock
        # boundary in the naive frame (no DST transitions to worry about),
        # then restore the original offset.
        return create_datetime_instance(
            _end_of_period_fixed(dt.replace(tzinfo=None), period).replace(
                tzinfo=dt.tzinfo
            )
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
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

    return create_datetime_instance(_whenever_to_stdlib(zdt))


def _end_of_period_fixed(dt: datetime.datetime, period: str) -> datetime.datetime:
    """`end_of_period` for a naive datetime, via plain stdlib arithmetic."""
    if period == "second":
        return dt.replace(microsecond=999999)
    if period == "minute":
        return dt.replace(second=59, microsecond=999999)
    if period == "hour":
        return dt.replace(minute=59, second=59, microsecond=999999)
    if period == "day":
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    if period == "week":
        days_till_end_of_week = 7 - dt.isoweekday()
        return (dt + datetime.timedelta(days=days_till_end_of_week)).replace(
            hour=23,
            minute=59,
            second=59,
            microsecond=999999,
        )
    raise ValueError(f"Invalid period: {period}")


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
    if sys.version_info < (3, 13):
        return DateTime.instance(dt).start_of("day")
    dt = _zdt_or_fixed_offset(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    if not isinstance(dt.tzinfo, ZoneInfo):
        # Fixed-offset and other non-IANA tzinfo: the wall-clock boundary is
        # just the same calendar day at midnight in that offset.
        return create_datetime_instance(
            dt.replace(hour=0, minute=0, second=0, microsecond=0)
        )

    zdt = _whenever_zdt_from_py(dt)
    zdt = (
        zdt.start_of("day")
        if callable(getattr(zdt, "start_of", None))
        else zdt.start_of_day()
    )

    return create_datetime_instance(_whenever_to_stdlib(zdt))


def earliest_possible_datetime() -> datetime.datetime:
    return datetime.datetime.min.replace(tzinfo=ZoneInfo("UTC"))


@contextmanager
def travel_to(dt: Any):
    """Freeze `whenever`'s clock at `dt` so every caller of `now()` sees it.

    Also freezes Pendulum's clock on Python 3.11 and 3.12 during the
    deprecation window. Those versions require the optional `pendulum[test]`
    extra, which is included in Prefect's development dependencies.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    _instant_from_py = Instant if _WHENEVER_NEW_API else Instant.from_py_datetime
    pendulum_clock = (
        pendulum.travel_to(dt, freeze=True)
        if sys.version_info < (3, 13)
        else nullcontext()
    )
    with patch_current_time(_instant_from_py(dt), keep_ticking=False), pendulum_clock:
        yield


def in_local_tz(dt: datetime.datetime) -> datetime.datetime:
    if sys.version_info < (3, 13):
        return DateTime.instance(dt).in_tz(pendulum.local_timezone())
    if dt.tzinfo is None:
        wdt = _whenever_pdt_from_py(dt).assume_system_tz()
    else:
        if not isinstance(dt.tzinfo, ZoneInfo):
            if key := getattr(dt.tzinfo, "key", None):
                dt = dt.replace(tzinfo=ZoneInfo(key))
            else:
                utc_dt = dt.astimezone(datetime.UTC)
                dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))

        wdt = _whenever_zdt_from_py(dt).to_system_tz()

    return create_datetime_instance(_whenever_to_stdlib(wdt))


def to_datetime_string(dt: datetime.datetime, include_tz: bool = True) -> str:
    if include_tz:
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    else:
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def _validate_positive_interval(v: Interval) -> Interval:
    if isinstance(v, datetime.timedelta):
        if v <= datetime.timedelta(0):
            raise ValueError("interval must be positive")
    elif _WHENEVER_NEW_API:
        if isinstance(v, ItemizedDelta):
            if v.sign() <= 0:
                raise ValueError("interval must be positive")
            date, time = v.date_and_time_parts()
            has_calendar_units = date and any(
                date.get(unit) for unit in ("years", "months", "weeks", "days")
            )
            if not has_calendar_units and time and time.total("nanoseconds") < 1000:
                raise ValueError("interval must be at least one microsecond")
    elif isinstance(v, DateTimeDelta):
        _months, _days, _secs, _nanos = v.in_months_days_secs_nanos()
        if _months <= 0 and _days <= 0 and _secs <= 0 and _nanos <= 0:
            raise ValueError("interval must be positive")
    return v


PositiveInterval = Annotated[Interval, AfterValidator(_validate_positive_interval)]
