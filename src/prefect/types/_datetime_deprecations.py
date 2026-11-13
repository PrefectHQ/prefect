"""Temporary Pendulum deprecation handling for Python 3.11 and 3.12.

Remove this module when those versions switch to stdlib datetime behavior.
Pickle paths remain in `prefect.types._datetime` for compatibility.

Warnings apply to whole methods, including stdlib-compatible calls to shared
methods with Pendulum-specific defaults or accepted arguments. Formatting,
extraction, conversion, and arithmetic remain quiet. This is a targeted migration
notice, not an exhaustive detector of every difference between the libraries.

Prefect's own code must invoke warned members via `_datetime._pendulum_call`
so users only see warnings for calls they make themselves.
"""

from __future__ import annotations

import datetime
import inspect
import operator
import os
import sys
import warnings
from collections.abc import Callable
from functools import partial, wraps
from typing import Any, SupportsIndex, TypeVar

import pendulum
import pendulum.tz
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema as _core_schema
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
_PICKLE_MODULE = "prefect.types._datetime"
_PendulumType = TypeVar("_PendulumType")

# Shared methods with Pendulum-specific timezone defaults or accepted arguments.
# Date's other constructors delegate to stdlib; datetime's fromordinal and
# utcfromtimestamp explicitly preserve naive results. Extraction and astimezone
# retain their existing behavior without adding warnings.
_SHARED_METHODS_TO_WARN = {
    datetime.datetime: {
        "now",
        "fromtimestamp",
        "today",
        "utcnow",
        "strptime",
        "combine",
        "replace",
    },
    datetime.date: {"replace"},
    datetime.time: {"replace"},
}


def _warn_pendulum_member(name: str, *, timezone_argument: bool = False) -> None:
    # Keep the keyword accepted by previously serialized method wrappers.
    warnings.warn(
        f"Pendulum datetime member {name!r} has deprecated Pendulum-specific "
        "behavior. Some calls are also compatible with standard-library datetime "
        "types. Pendulum "
        "datetime behavior on Python 3.11 and 3.12 will be retained for "
        "at least six months and three minor version increases after the "
        "deprecation release, whichever is longer; a later minor release "
        "will return standard-library datetime types without "
        "Pendulum-specific behavior.",
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
    """Decorate extensions and audited shared methods once per subclass."""

    def decorate(cls: type[_PendulumType]) -> type[_PendulumType]:
        # Moving this implementation must not change class or method pickle paths.
        cls.__module__ = _PICKLE_MODULE
        for member in vars(cls).values():
            function = member.__func__ if isinstance(member, classmethod) else member
            if inspect.isfunction(function):
                function.__module__ = cls.__module__
        decorated: dict[Callable[..., Any], Callable[..., Any]] = {}
        shared_methods = _SHARED_METHODS_TO_WARN.get(stdlib, set())
        for name in dir(cls):
            if name.startswith("_") or (
                name in dir(stdlib) and name not in shared_methods
            ):
                continue
            member = inspect.getattr_static(cls, name)
            function = member.__func__ if isinstance(member, classmethod) else member
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
                classmethod(wrapped) if isinstance(member, classmethod) else wrapped,
            )
        return cls

    return decorate


@_deprecated_pendulum_members(datetime.datetime)
class DateTime(PydanticDateTime):
    """Pendulum `DateTime` that warns on deprecated method calls."""

    @classmethod
    def _validate(
        cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
    ) -> DateTime:
        """Retain the warning-enabled type after upstream validation."""
        return _PDT_INSTANCE(cls, super()._validate(value, handler))

    def date(self) -> Date:
        """Return the date portion, preserving the deprecation notice."""
        return _wrap_pendulum_value(super().date())

    setattr(date, "__wrapped__", PydanticDateTime.date)
    setattr(date, "__prefect_task_source__", PydanticDateTime.date)

    def time(self) -> _Time:
        """Return the time portion, preserving the deprecation notice."""
        return _wrap_pendulum_value(super().time())

    setattr(time, "__wrapped__", PydanticDateTime.time)
    setattr(time, "__prefect_task_source__", PydanticDateTime.time)

    def __sub__(self, other: datetime.datetime | datetime.timedelta) -> Any:
        """Retain warnings when subtracting a plain naive datetime."""
        return _wrap_pendulum_value(super().__sub__(other))

    setattr(__sub__, "__wrapped__", PydanticDateTime.__sub__)
    setattr(__sub__, "__prefect_task_source__", PydanticDateTime.__sub__)


@_deprecated_pendulum_members(datetime.date)
class Date(PydanticDate):
    """Pendulum `Date` that warns on deprecated method calls."""

    @classmethod
    def _validate(
        cls, value: Any, handler: _core_schema.ValidatorFunctionWrapHandler
    ) -> Date:
        """Retain the warning-enabled type after upstream validation."""
        validated = super()._validate(value, handler)
        return cls(validated.year, validated.month, validated.day)


@_deprecated_pendulum_members(datetime.time)
class _Time(pendulum.Time):
    """Pendulum `Time` that warns on deprecated method calls."""

    def __reduce_ex__(self, protocol: SupportsIndex) -> Any:
        # The public DateTime.time method also exists on older readers.
        if self.tzinfo is not None or self.fold:
            return partial(datetime.time.replace, tzinfo=self.tzinfo, fold=self.fold), (
                _Time(self.hour, self.minute, self.second, self.microsecond),
            )
        return DateTime.time, (
            DateTime(1970, 1, 1, self.hour, self.minute, self.second, self.microsecond),
        )


@_deprecated_pendulum_members(datetime.timedelta)
class Duration(PydanticDuration):
    """Pendulum `Duration` that warns on Pendulum-only member calls."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> _core_schema.CoreSchema:
        schema = super().__get_pydantic_core_schema__(source_type, handler)
        serializer = getattr(PydanticDuration, "to_iso8601_string", None)
        if serializer is not None:
            schema["serialization"] = _core_schema.plain_serializer_function_ser_schema(
                serializer, when_used="json-unless-none"
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
class _Interval(pendulum.Interval):
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
    if isinstance(value, pendulum.Time):
        if isinstance(value, _Time):
            return value
        return _Time(
            value.hour,
            value.minute,
            value.second,
            value.microsecond,
            tzinfo=value.tzinfo,
            fold=value.fold,
        )
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
_Time.min = _wrap_pendulum_value(_Time.min)
_Time.max = _wrap_pendulum_value(_Time.max)
_Time.resolution = _wrap_pendulum_value(_Time.resolution)
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

# Cloudpickle also records these helpers when serializing decorated class methods.
for _function in (
    _warn_pendulum_member,
    _deprecated_pendulum_method,
    _deprecated_pendulum_members,
    _datetime_instance,
    _wrap_pendulum_value,
):
    _function.__module__ = _PICKLE_MODULE
del _function
