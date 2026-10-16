from __future__ import annotations

import datetime
import os
import sys
import warnings
from contextlib import contextmanager
from typing import Annotated, Any, ClassVar, Union, cast
from unittest import mock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import humanize
from dateutil.parser import parse
from pydantic import AfterValidator
from pydantic_core import core_schema as _core_schema
from typing_extensions import TypeAlias

if sys.version_info >= (3, 13):
    from pydantic import GetCoreSchemaHandler
    from whenever import DateTimeDelta
    from whenever import ZonedDateTime as _ZDTProbe

    # True on whenever >= 0.10.0, which introduced ZonedDateTime(stdlib_dt),
    # start_of("day"), and to_stdlib(). False on 0.7.x–0.9.x.
    _WHENEVER_NEW_API: bool = hasattr(_ZDTProbe, "to_stdlib")
    del _ZDTProbe

    class _DateTime(datetime.datetime):
        """`datetime.datetime` with a Pydantic schema that coerces naive to UTC.

        On Python <= 3.12 the pendulum-backed `PydanticDateTime` enforces
        tz-awareness during validation. This class is the 3.13+ equivalent so
        any field typed as `DateTime` gets the same guarantee instead of
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

    DateTime: TypeAlias = _DateTime
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

    _PENDULUM_PACKAGE_DIR = os.path.dirname(pendulum.__file__) + os.sep

    def _warn_pendulum_member(name: str) -> None:
        warnings.warn(
            f"Pendulum datetime member {name!r} is deprecated. Pendulum "
            "datetime behavior on Python 3.11 and 3.12 will be retained for "
            "at least six months and three minor version increases after the "
            "deprecation release, whichever is longer; a later minor release "
            "will return standard-library datetime types without "
            "Pendulum-specific members.",
            DeprecationWarning,
            stacklevel=3,
        )

    def _pendulum_only_members(native: type, stdlib: type) -> frozenset[str]:
        """Members Pendulum provides beyond the equivalent stdlib type."""
        return frozenset(
            name
            for name in dir(native)
            if not name.startswith("__") and name not in dir(stdlib)
        )

    class _DeprecatedMemberCall:
        """Callable proxy for a Pendulum-only member that warns when called.

        Calls originating inside the `pendulum` package are Pendulum methods
        delegating to each other and do not warn; every other caller —
        including Prefect code invoking a user-supplied bound method — warns.
        Prefect's own internal calls go through `_pendulum_call` instead. The
        proxy pickles back to a plain attribute lookup so Pendulum-only
        bound methods remain serializable across process boundaries.
        """

        def __init__(self, obj: Any, name: str, member: Any) -> None:
            self._obj = obj
            self._name = name
            self._member = member
            self.__name__ = name
            self.__doc__ = getattr(member, "__doc__", None)
            self.__wrapped__ = member

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            caller_file = sys._getframe(1).f_code.co_filename
            if not caller_file.startswith(_PENDULUM_PACKAGE_DIR):
                _warn_pendulum_member(self._name)
            return self._member(*args, **kwargs)

        def __reduce__(self) -> Any:
            return (getattr, (self._obj, self._name))

    class _PendulumDeprecationMixin:
        """Warns when a Pendulum-only member is called.

        Only callable members that have no standard-library counterpart
        (e.g. `in_tz`, `add`, `diff`, `start_of`) warn; plain attribute
        access and methods shared with `datetime` stay quiet.
        """

        _pendulum_only_members: ClassVar[frozenset[str]]

        def __getattribute__(self, name: str) -> Any:
            attr = super().__getattribute__(name)
            if callable(attr) and name in type(self)._pendulum_only_members:
                return _DeprecatedMemberCall(self, name, attr)
            return attr

    class DateTime(_PendulumDeprecationMixin, PydanticDateTime):  # type: ignore[no-redef]
        """Pendulum `DateTime` that warns on Pendulum-only member calls."""

        _pendulum_only_members = _pendulum_only_members(
            pendulum.DateTime, datetime.datetime
        )

        @classmethod
        def _validate(
            cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
        ) -> DateTime:
            """Retain the warning-enabled type after upstream validation."""
            return cls.instance(super()._validate(value, handler))

    class Date(_PendulumDeprecationMixin, PydanticDate):  # type: ignore[no-redef]
        """Pendulum `Date` that warns on Pendulum-only member calls."""

        _pendulum_only_members = _pendulum_only_members(pendulum.Date, datetime.date)

        @classmethod
        def _validate(
            cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
        ) -> Date:
            """Retain the warning-enabled type after upstream validation."""
            validated = super()._validate(value, handler)
            return cls(validated.year, validated.month, validated.day)

    class Duration(_PendulumDeprecationMixin, PydanticDuration):  # type: ignore[no-redef]
        """Pendulum `Duration` that warns on Pendulum-only member calls."""

        _pendulum_only_members = _pendulum_only_members(
            pendulum.Duration, datetime.timedelta
        )

        @classmethod
        def _validate(
            cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
        ) -> Duration:
            """Retain the warning-enabled type and its calendar components."""
            validated = super()._validate(value, handler)
            return cls(
                years=validated.years,
                months=validated.months,
                weeks=validated.weeks,
                days=validated.remaining_days,
                hours=validated.hours,
                minutes=validated.minutes,
                seconds=validated.remaining_seconds,
                microseconds=validated.microseconds,
            )

    Interval: TypeAlias = datetime.timedelta


def _pendulum_call(obj: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    """Invoke a Pendulum-only member without the deprecation warning.

    For internal Prefect use: bypasses the `_PendulumDeprecationMixin`
    proxy so Prefect's own machinery can keep using Pendulum behavior
    silently. `obj` may be any Pendulum value.
    """
    return object.__getattribute__(obj, name)(*args, **kwargs)


def parse_datetime(dt: str) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        parsed_dt = parse(dt)
        if parsed_dt.tzinfo is None:
            # Assume UTC if no timezone is provided
            return parsed_dt.replace(tzinfo=ZoneInfo("UTC"))
        else:
            return parsed_dt
    else:
        return cast(datetime.datetime, DateTime.instance(pendulum.parse(dt)))


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

    return DateTime.instance(pendulum.from_timestamp(ts, tz))


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
    return _pendulum_call(pendulum_dt, "diff_for_humans", other=pendulum_other)


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
        return DateTime.instance(pendulum.now(tz))


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
        return DateTime.instance(
            _pendulum_call(DateTime.instance(dt), "end_of", period)
        )


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
        return DateTime.instance(
            _pendulum_call(DateTime.instance(dt), "start_of", "day")
        )


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
        return DateTime.instance(
            _pendulum_call(DateTime.instance(dt), "in_tz", pendulum.tz.local_timezone())
        )


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
