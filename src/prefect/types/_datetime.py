from __future__ import annotations

import datetime
import inspect
import operator
import os
import sys
import warnings
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Annotated, Any, SupportsIndex, TypeVar, Union, cast
from unittest import mock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

import humanize
from dateutil.parser import parse
from pydantic import AfterValidator, GetCoreSchemaHandler
from pydantic_core import core_schema as _core_schema
from typing_extensions import TypeAlias

if sys.version_info >= (3, 13):
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
    _PendulumType = TypeVar("_PendulumType")

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

    def _deprecated_pendulum_method(member: Callable[..., Any]) -> Callable[..., Any]:
        """Add a call-time warning while retaining ordinary method binding."""

        @wraps(member)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            caller_file = sys._getframe(1).f_code.co_filename
            if not caller_file.startswith(_PENDULUM_PACKAGE_DIR):
                _warn_pendulum_member(member.__name__)
            return _wrap_pendulum_value(member(*args, **kwargs))

        # Task keys and input hashes retain the original method's code.
        setattr(wrapper, "__prefect_task_source__", member)
        return wrapper

    def _deprecated_pendulum_members(
        stdlib: type,
    ) -> Callable[[type[_PendulumType]], type[_PendulumType]]:
        """Decorate Pendulum-only methods on Prefect's subclasses once."""

        def decorate(cls: type[_PendulumType]) -> type[_PendulumType]:
            decorated: dict[Callable[..., Any], Callable[..., Any]] = {}
            for name in dir(cls):
                if name.startswith("_") or name in dir(stdlib):
                    continue
                member = inspect.getattr_static(cls, name)
                function = (
                    member.__func__ if isinstance(member, classmethod) else member
                )
                if not callable(function):
                    continue
                # Aliases share one function so equality and pickle lookup agree.
                if function not in decorated:
                    wrapped = _deprecated_pendulum_method(function)
                    # Pickle must find the decorator on the Prefect subclass.
                    wrapped.__name__ = name
                    wrapped.__qualname__ = f"{cls.__qualname__}.{name}"
                    wrapped.__module__ = cls.__module__
                    decorated[function] = wrapped
                wrapped = decorated[function]
                setattr(
                    cls,
                    name,
                    classmethod(wrapped)
                    if isinstance(member, classmethod)
                    else wrapped,
                )
            return cls

        return decorate

    @_deprecated_pendulum_members(datetime.datetime)
    class DateTime(PydanticDateTime):  # type: ignore[no-redef]
        """Pendulum `DateTime` that warns on Pendulum-only member calls."""

        @classmethod
        def _validate(
            cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
        ) -> DateTime:
            """Retain the warning-enabled type after upstream validation."""
            return _PDT_INSTANCE(cls, super()._validate(value, handler))

        def date(self) -> Date:
            """Return the date portion, preserving the deprecation notice."""
            return _wrap_pendulum_value(super().date())

        def __sub__(self, other: datetime.datetime | datetime.timedelta) -> Any:
            """Retain warnings when subtracting a plain naive datetime."""
            return _wrap_pendulum_value(super().__sub__(other))

    @_deprecated_pendulum_members(datetime.date)
    class Date(PydanticDate):  # type: ignore[no-redef]
        """Pendulum `Date` that warns on Pendulum-only member calls."""

        @classmethod
        def _validate(
            cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
        ) -> Date:
            """Retain the warning-enabled type after upstream validation."""
            validated = super()._validate(value, handler)
            return cls(validated.year, validated.month, validated.day)

    @_deprecated_pendulum_members(datetime.timedelta)
    class Duration(PydanticDuration):  # type: ignore[no-redef]
        """Pendulum `Duration` that warns on Pendulum-only member calls."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, source_type: Any, handler: GetCoreSchemaHandler
        ) -> _core_schema.CoreSchema:
            schema = super().__get_pydantic_core_schema__(source_type, handler)
            serializer = getattr(PydanticDuration, "to_iso8601_string", None)
            if serializer is not None:
                schema["serialization"] = (
                    _core_schema.plain_serializer_function_ser_schema(
                        serializer, when_used="json-unless-none"
                    )
                )
            return schema

        @classmethod
        def _from_pendulum(cls, value: pendulum.Duration) -> Duration:
            # Component properties use floats; the constructor signature retains
            # exact inputs, including calendar units and timedelta.max.
            return cls(**getattr(value, "_signature"))

        @classmethod
        def _validate(
            cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
        ) -> Duration:
            """Retain the warning-enabled type and its calendar components."""
            validated = super()._validate(value, handler)
            return cls._from_pendulum(validated)

    @_deprecated_pendulum_members(datetime.timedelta)
    class _Interval(pendulum.Interval):  # type: ignore[no-redef]
        """Pendulum `Interval` that warns on Pendulum-only member calls.

        Produced by `DateTime` subtraction and `diff()` so derived values
        keep the deprecation notice.
        """

        def __reduce_ex__(self, protocol: SupportsIndex) -> Any:
            # Older Prefect versions can reconstruct intervals through standard
            # arithmetic without importing this new private class.
            start, end, absolute = pendulum.Interval._getstate(self, protocol)
            if absolute:
                return abs, (type(self)(start, end),)
            return operator.sub, (end, start)

    _PDT_INSTANCE = PydanticDateTime.instance.__func__

    def _datetime_instance(value: datetime.datetime) -> DateTime:
        """Wrap a datetime in the warning-enabled `DateTime`.

        Bypasses the class-level deprecation decorator for Prefect's own calls.
        """
        return _PDT_INSTANCE(DateTime, value)

    def _wrap_pendulum_value(value: Any) -> Any:
        """Re-wrap a Pendulum result in its warning-enabled Prefect type.

        Derived values (e.g. `date()`, subtraction, `diff()`) come back as
        plain Pendulum objects; converting them keeps the deprecation notice
        on their Pendulum-only members too.
        """
        if isinstance(value, pendulum.DateTime):
            if isinstance(value, DateTime):
                return value
            return _PDT_INSTANCE(DateTime, value, tz=value.tzinfo)
        if isinstance(value, pendulum.Date):
            if isinstance(value, Date):
                return value
            return Date(value.year, value.month, value.day)
        if isinstance(value, pendulum.Interval):
            if isinstance(value, _Interval):
                return value
            # Pendulum's pickle state preserves the original interval direction.
            start, end, absolute = pendulum.Interval._getstate(value)
            return _Interval(
                start=_wrap_pendulum_value(start),
                end=_wrap_pendulum_value(end),
                absolute=absolute,
            )
        if isinstance(value, pendulum.Duration):
            if isinstance(value, Duration):
                return value
            return Duration._from_pendulum(value)
        return value

    # Inherited constants hold plain Pendulum values; wrap them once so their
    # Pendulum-only methods retain the same deprecation behavior.
    DateTime.EPOCH = _wrap_pendulum_value(DateTime.EPOCH)
    DateTime.min = _wrap_pendulum_value(DateTime.min)
    DateTime.max = _wrap_pendulum_value(DateTime.max)
    # Use the exact stdlib bounds: Pendulum's component properties round up
    # at timedelta.max, overflowing when reconstructed by the wrapper.
    for _name in ("min", "max", "resolution"):
        _value = getattr(datetime.timedelta, _name)
        setattr(
            Duration,
            _name,
            Duration(
                days=_value.days,
                seconds=_value.seconds,
                microseconds=_value.microseconds,
            ),
        )
    del _name, _value

    Interval: TypeAlias = datetime.timedelta


def _pendulum_call(obj: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    """Invoke a Pendulum-only member without the deprecation warning.

    For internal Prefect use: bypasses the deprecation decorator
    so Prefect's own machinery can keep using Pendulum behavior
    silently. `obj` may be any Pendulum value.
    """
    member = getattr(obj, name)
    original = getattr(member, "__prefect_task_source__", None)
    if original is not None and original is getattr(member, "__wrapped__", None):
        return original(member.__self__, *args, **kwargs)
    return member(*args, **kwargs)


def parse_datetime(dt: str) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        parsed_dt = parse(dt)
        if parsed_dt.tzinfo is None:
            # Assume UTC if no timezone is provided
            return parsed_dt.replace(tzinfo=ZoneInfo("UTC"))
        else:
            return parsed_dt
    else:
        return cast(datetime.datetime, _wrap_pendulum_value(pendulum.parse(dt)))


def get_timezones() -> tuple[str, ...]:
    return tuple(available_timezones())


def create_datetime_instance(v: datetime.datetime) -> datetime.datetime:
    if sys.version_info >= (3, 13):
        if v.tzinfo is None:
            # Assume UTC if no timezone is provided
            return v.replace(tzinfo=ZoneInfo("UTC"))
        else:
            return v

    return _datetime_instance(v)


def from_timestamp(ts: float, tz: str | Any = "UTC") -> datetime.datetime:
    if sys.version_info >= (3, 13):
        if not isinstance(tz, str):
            # Handle pendulum edge case
            tz = tz.name
        return datetime.datetime.fromtimestamp(ts, ZoneInfo(tz))

    return _datetime_instance(pendulum.from_timestamp(ts, tz))


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
    pendulum_dt = _datetime_instance(dt.astimezone(ZoneInfo("UTC")))
    pendulum_other = (
        _datetime_instance(other.astimezone(ZoneInfo("UTC"))) if other else None
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
        return _datetime_instance(pendulum.now(tz))


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
        return _datetime_instance(
            _pendulum_call(_datetime_instance(dt), "end_of", period)
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
        return _datetime_instance(
            _pendulum_call(_datetime_instance(dt), "start_of", "day")
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
        return _datetime_instance(
            _pendulum_call(
                _datetime_instance(dt), "in_tz", pendulum.tz.local_timezone()
            )
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
