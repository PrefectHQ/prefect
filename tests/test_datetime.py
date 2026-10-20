"""Tests for prefect.types._datetime.

These tests are intentionally version-agnostic: they run on all supported
Python versions without any skips. On Python < 3.13 the pendulum backend is
exercised; on Python >= 3.13 the whenever backend is exercised. If all
assertions pass across the CI matrix we have behavioral parity between the
two backends.
"""

import base64
import datetime
import gc
import inspect
import io
import pickle
import subprocess
import sys
import warnings
import weakref
from collections.abc import Callable
from functools import wraps
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel, GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema

import prefect.runtime.flow_run as runtime_flow_run
import prefect.types._datetime
from prefect import task
from prefect._internal.compatibility.deprecated import generate_deprecation_message
from prefect.client.schemas.objects import FlowRun
from prefect.context import TaskRunContext
from prefect.serializers import PickleSerializer
from prefect.server.schemas.schedules import CronSchedule, IntervalSchedule
from prefect.tasks import task_input_hash
from prefect.types import _datetime as datetime_module
from prefect.types._datetime import (
    Date,
    DateTime,
    Duration,
    _pendulum_call,
    create_datetime_instance,
    end_of_period,
    from_timestamp,
    human_friendly_diff,
    in_local_tz,
    now,
    parse_datetime,
    start_of_day,
    travel_to,
)

if sys.version_info < (3, 13):
    import pendulum
    from pydantic_extra_types.pendulum_dt import Date as PydanticDate
    from pydantic_extra_types.pendulum_dt import DateTime as PydanticDateTime
    from pydantic_extra_types.pendulum_dt import Duration as PydanticDuration

# Saturday 2024-06-15 14:30:45 America/New_York (UTC-4, i.e. EDT)
FIXED = datetime.datetime(2024, 6, 15, 14, 30, 45, tzinfo=ZoneInfo("America/New_York"))
EDT = datetime.timedelta(hours=-4)


class TestNow:
    def test_returns_aware_datetime(self):
        result = now("UTC")
        assert result.tzinfo is not None

    def test_is_close_to_current_time(self):
        before = datetime.datetime.now(ZoneInfo("UTC"))
        result = now("UTC")
        after = datetime.datetime.now(ZoneInfo("UTC"))
        assert before <= result.astimezone(ZoneInfo("UTC")) <= after


class TestStartOfDay:
    def test_full_datetime(self):
        result = start_of_day(FIXED)

        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0
        assert result.tzinfo is not None
        assert result.utcoffset() == FIXED.utcoffset()


class TestEndOfPeriod:
    @pytest.mark.parametrize(
        "period, expected",
        [
            (
                "second",
                datetime.datetime(
                    2024, 6, 15, 14, 30, 45, 999999, tzinfo=ZoneInfo("America/New_York")
                ),
            ),
            (
                "minute",
                datetime.datetime(
                    2024, 6, 15, 14, 30, 59, 999999, tzinfo=ZoneInfo("America/New_York")
                ),
            ),
            (
                "hour",
                datetime.datetime(
                    2024, 6, 15, 14, 59, 59, 999999, tzinfo=ZoneInfo("America/New_York")
                ),
            ),
            (
                "day",
                datetime.datetime(
                    2024, 6, 15, 23, 59, 59, 999999, tzinfo=ZoneInfo("America/New_York")
                ),
            ),
            (
                "week",
                # June 15 (Sat) → end of ISO week = Sunday June 16
                datetime.datetime(
                    2024, 6, 16, 23, 59, 59, 999999, tzinfo=ZoneInfo("America/New_York")
                ),
            ),
        ],
    )
    def test_full_datetime(self, period: str, expected: datetime.datetime):
        result = end_of_period(FIXED, period)

        assert result.year == expected.year
        assert result.month == expected.month
        assert result.day == expected.day
        assert result.hour == expected.hour
        assert result.minute == expected.minute
        assert result.second == expected.second
        assert result.microsecond == expected.microsecond
        assert result.tzinfo is not None
        assert result.utcoffset() == EDT

    def test_invalid_period_raises(self):
        # NOTE: pendulum (Python < 3.13) silently ignores unknown periods, so
        # this assertion only holds on Python >= 3.13 (whenever backend).
        import sys

        if sys.version_info >= (3, 13):
            with pytest.raises(ValueError, match="Invalid period"):
                end_of_period(FIXED, "century")


class TestInLocalTz:
    def test_returns_aware_datetime(self):
        result = in_local_tz(FIXED)
        assert result.tzinfo is not None

    def test_preserves_utc_instant(self):
        result = in_local_tz(FIXED)
        assert result.astimezone(ZoneInfo("UTC")) == FIXED.astimezone(ZoneInfo("UTC"))

    def test_naive_datetime(self):
        naive = datetime.datetime(2024, 6, 15, 14, 30, 45)
        result = in_local_tz(naive)
        assert result.tzinfo is not None


class TestDateTimeTypeAlias:
    """`DateTime` is the type alias used for Pydantic-validated datetime fields.

    On Python <= 3.12 it is pendulum-backed (`PydanticDateTime`); on Python
    >= 3.13 it is a `datetime.datetime` subclass with a Pydantic schema that
    enforces tz-awareness. These tests guard parity across versions — a naive
    input must come out tz-aware regardless of which backend is active. See
    #21949.
    """

    def test_naive_value_is_coerced_to_utc(self):
        class Model(BaseModel):
            when: DateTime

        naive = datetime.datetime(2024, 6, 15, 14, 30, 45)
        result = Model(when=naive).when

        assert result.tzinfo is not None
        assert result.utcoffset() == datetime.timedelta(0)
        # Wall-clock components are preserved (treated as UTC, not converted).
        assert (result.year, result.month, result.day) == (2024, 6, 15)
        assert (result.hour, result.minute, result.second) == (14, 30, 45)

    def test_aware_value_is_preserved(self):
        class Model(BaseModel):
            when: DateTime

        aware = datetime.datetime(2024, 6, 15, 14, 30, 45, tzinfo=ZoneInfo("UTC"))
        result = Model(when=aware).when

        assert result.utcoffset() == datetime.timedelta(0)
        assert result.hour == 14

    def test_non_utc_aware_value_is_preserved(self):
        class Model(BaseModel):
            when: DateTime

        eastern = datetime.timezone(datetime.timedelta(hours=-5))
        aware = datetime.datetime(2024, 6, 15, 14, 30, 45, tzinfo=eastern)
        result = Model(when=aware).when

        assert result.utcoffset() == aware.utcoffset()
        assert result.hour == 14

    def test_naive_iso_string_is_coerced_to_utc(self):
        """Pydantic parses ISO strings without offsets into naive datetimes;
        the type alias must still produce a tz-aware result."""

        class Model(BaseModel):
            when: DateTime

        result = Model(when="2024-06-15T14:30:45").when
        assert result.tzinfo is not None
        assert result.utcoffset() == datetime.timedelta(0)


def test_pendulum_deprecation_notice_matches_python_version():
    code = (
        "from datetime import UTC, datetime\n"
        "import prefect\n"
        "from prefect.types._datetime import create_datetime_instance\n"
        "dt = create_datetime_instance(datetime(2024, 1, 1, tzinfo=UTC))\n"
        "# stdlib members must not warn\n"
        "dt.isoformat()\n"
        "# Pendulum-only member must warn\n"
        "if hasattr(dt, 'in_tz'):\n"
        "    dt.in_tz('UTC')\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "always::DeprecationWarning",
            "-c",
            code,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    if sys.version_info < (3, 13):
        assert result.stderr.count("Pendulum datetime member 'in_tz'") == 1
        assert "six months and three minor" in result.stderr
        assert "datetime" in result.stderr
    else:
        assert "Pendulum datetime member" not in result.stderr


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_no_pendulum_deprecation_warning_on_import():
    result = subprocess.run(
        [
            sys.executable,
            "-W",
            "always::DeprecationWarning",
            "-c",
            "import prefect",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Pendulum datetime member" not in result.stderr


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_pendulum_only_bound_method_remains_picklable():
    restored = pickle.loads(pickle.dumps(now("UTC").add))
    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'add'"):
        assert restored(days=1) > now("UTC")


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_prefect_helpers_do_not_emit_pendulum_warnings():
    """Prefect's internal Pendulum-only calls must not warn — even under
    `-W error::DeprecationWarning` — since callers never invoked one."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        start_of_day(FIXED)
        end_of_period(FIXED, "day")
        in_local_tz(FIXED)
        human_friendly_diff(FIXED)
        value = create_datetime_instance(FIXED)
        start_of_day(value)
        end_of_period(value, "day")
        in_local_tz(value)
        human_friendly_diff(value)
        TypeAdapter(DateTime).dump_json(TypeAdapter(DateTime).validate_python(value))


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
async def test_prefect_call_sites_do_not_emit_pendulum_warnings(
    monkeypatch: pytest.MonkeyPatch,
):
    """Pendulum-only calls outside `types/_datetime.py` must go through
    `_pendulum_call`. The pytest config ignores these warnings globally, so
    this test re-enables them for representative internal call sites."""
    start = create_datetime_instance(FIXED)
    naive = _pendulum_call(start, "naive")
    monkeypatch.setattr(runtime_flow_run, "parse_datetime", lambda _: naive)
    end = start + datetime.timedelta(days=2)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error", message="Pendulum datetime member", category=DeprecationWarning
        )
        await IntervalSchedule(
            interval=datetime.timedelta(hours=1),
            anchor_date=start,
            timezone="America/New_York",
        ).get_dates(n=3, start=start, end=end)
        await IntervalSchedule(
            interval=datetime.timedelta(days=1),
            anchor_date=start,
            timezone="America/New_York",
        ).get_dates(n=3, start=start, end=end)
        await CronSchedule(cron="0 * * * *", timezone="America/New_York").get_dates(
            n=3, start=start, end=end
        )
        # Covers the naive-input branch, which real ISO strings never reach.
        runtime_flow_run._parse_datetime_UTC("2024-06-15T14:30:45")
        generate_deprecation_message("thing", start_date=start)


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
@pytest.mark.parametrize(
    "member, kwargs", [("add", {"days": 1}), ("replace", {"year": 2025})]
)
def test_pendulum_method_invoked_through_prefect_machinery_warns(
    member: str, kwargs: dict[str, int]
):
    """A user-supplied bound method invoked via Prefect (e.g.
    the task engine's `call_with_parameters`) still warns."""
    from prefect.utilities.callables import call_with_parameters

    with pytest.warns(DeprecationWarning, match=f"Pendulum datetime member '{member}'"):
        call_with_parameters(getattr(now("UTC"), member), kwargs)


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_pendulum_only_classmembers_warn():
    """Pendulum-only constructors accessed on the class warn like
    instance-level calls (`DateTime.instance`, `DateTime.create`)."""
    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'instance'"):
        DateTime.instance(datetime.datetime.now(datetime.UTC))


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_pendulum_method_qualnames_are_unique():
    """Decorated members carry distinct `__qualname__` values so callers that
    key on them (e.g. `task()` task keys) don't collide."""
    dt = now("UTC")
    assert dt.add.__qualname__ != dt.subtract.__qualname__
    assert dt.add.__name__ == "add"


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_pendulum_derived_values_retain_deprecation_notice():
    """Values derived from Prefect-vended datetimes warn on Pendulum-only
    members too: `date()`, subtraction, and `diff()` results."""
    dt = now("UTC")

    derived_date = dt.date()
    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'add'"):
        derived_date.add(days=1)

    derived_interval = dt - dt
    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'in_words'"):
        derived_interval.in_words()

    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'diff'"):
        derived_interval = dt.diff(dt)
    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'in_words'"):
        derived_interval.in_words()


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
@pytest.mark.parametrize(
    "minutes, expected", [(20, "in 20 minutes"), (-20, "20 minutes ago")]
)
def test_wrapped_interval_preserves_direction(minutes: int, expected: str):
    with travel_to(FIXED):
        assert (
            human_friendly_diff(FIXED + datetime.timedelta(minutes=minutes)) == expected
        )


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_date_subtraction_returns_interval():
    """`Date - Date` and `Date.diff` produce date-endpoint intervals; the
    wrap must not coerce endpoints to `DateTime`."""
    with pytest.warns(DeprecationWarning):
        interval = Date(2024, 1, 2).diff(Date(2024, 1, 1))
    assert isinstance(interval, pendulum.Interval)
    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'in_days'"):
        assert interval.in_days() == 1

    subtracted = Date(2024, 1, 2) - Date(2024, 1, 1)
    assert isinstance(subtracted, pendulum.Interval)
    with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'in_days'"):
        assert subtracted.in_days() == 1


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_parse_datetime_non_datetime_results():
    """`pendulum.parse` may yield non-DateTime results; they are wrapped in
    the warning-enabled types rather than raising AttributeError."""
    duration = parse_datetime("P1D")
    assert isinstance(duration, Duration)
    assert duration == datetime.timedelta(days=1)

    assert isinstance(parse_datetime("2024-01-01"), DateTime)


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_duration_pydantic_only_members_warn():
    """Members pydantic_extra_types adds beyond pendulum.Duration (e.g.
    `to_iso8601_string`) warn for direct calls but not during
    serialization."""
    with pytest.warns(
        DeprecationWarning, match="Pendulum datetime member 'to_iso8601_string'"
    ):
        assert Duration(days=1).to_iso8601_string() == "P1D"


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
def test_astimezone_preserves_timezone_for_pendulum_tz():
    """`astimezone` must keep producing aware datetimes even when the value
    carries a Pendulum `Timezone` (regression: numeric-slot overrides used
    to drop tzinfo from intermediate results)."""
    dt = now("UTC")
    result = dt.astimezone(ZoneInfo("America/New_York"))
    assert result.tzinfo is not None
    assert result.utcoffset() is not None


@pytest.mark.skipif(sys.version_info >= (3, 13), reason="legacy Pendulum API")
class TestPendulumCompatibility:
    @pytest.mark.parametrize(
        "action, count", [("ignore", 0), ("default", 1), ("always", 2)]
    )
    def test_method_warnings_respect_python_filters(self, action: str, count: int):
        value = create_datetime_instance(FIXED)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter(action, DeprecationWarning)
            for _ in range(2):
                value.replace(year=2025)
        assert len(caught) == count
        assert all(notice.category is DeprecationWarning for notice in caught)

    @pytest.mark.parametrize("member", ["now", "fromtimestamp", "combine", "replace"])
    @pytest.mark.parametrize("positional", [False, True])
    @pytest.mark.parametrize(
        "zone", ["UTC", 5.5, None, datetime.UTC, ZoneInfo("America/New_York")]
    )
    def test_shared_methods_warn_for_every_timezone_argument(
        self, member: str, positional: bool, zone: Any
    ):
        arguments = {
            "now": [],
            "fromtimestamp": [0],
            "combine": [datetime.date(2024, 6, 15), datetime.time(14, 30)],
            "replace": [None] * 7 if positional else [],
        }[member]
        parameter = "tzinfo" if member in ("combine", "replace") else "tz"
        kwargs = {} if positional else {parameter: zone}
        if positional:
            arguments.append(zone)
        target = create_datetime_instance(FIXED) if member == "replace" else DateTime
        native = pendulum.instance(FIXED) if member == "replace" else pendulum.DateTime
        with travel_to(FIXED):
            expected = getattr(native, member)(*arguments, **kwargs)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", DeprecationWarning)
                actual = getattr(target, member)(*arguments, **kwargs)

        assert len(caught) == 1
        assert f"Pendulum datetime member '{member}'" in str(caught[0].message)
        assert caught[0].filename == __file__
        assert isinstance(actual, DateTime)
        assert actual == expected
        assert actual.tzinfo == expected.tzinfo
        assert actual.fold == expected.fold

    @pytest.mark.parametrize("pendulum_time", [False, True])
    @pytest.mark.parametrize("zone", [None, datetime.UTC, ZoneInfo("America/New_York")])
    @pytest.mark.parametrize(
        "arguments", ["omitted", "positional", "keyword", "all_keywords"]
    )
    def test_combine_always_warns_and_retains_pendulum_semantics(
        self, pendulum_time: bool, zone: datetime.tzinfo | None, arguments: str
    ):
        date = datetime.date(2024, 6, 15)
        time_type = pendulum.Time if pendulum_time else datetime.time
        time = time_type(14, 30, tzinfo=zone)
        args: list[Any] = [date, time]
        kwargs: dict[str, Any] = {}
        if arguments == "positional":
            args.append(None)
        elif arguments == "keyword":
            kwargs["tzinfo"] = None
        elif arguments == "all_keywords":
            args = []
            kwargs = {"date": date, "time": time, "tzinfo": None}

        expected = pendulum.DateTime.combine(*args, **kwargs)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            actual = DateTime.combine(*args, **kwargs)

        assert len(caught) == 1
        assert "Pendulum datetime member 'combine'" in str(caught[0].message)
        assert caught[0].filename == __file__
        assert isinstance(actual, DateTime)
        assert actual == expected
        assert actual.tzinfo == expected.tzinfo
        assert actual.fold == expected.fold

    @pytest.mark.parametrize("positional", [False, True])
    @pytest.mark.parametrize(
        "zone", [datetime.UTC, datetime.timezone(datetime.timedelta(hours=2))]
    )
    def test_combine_warns_for_compatible_and_incompatible_timezone_overrides(
        self, positional: bool, zone: datetime.tzinfo
    ):
        args: list[Any] = [
            datetime.date(2024, 6, 15),
            datetime.time(14, 30, tzinfo=datetime.UTC),
        ]
        kwargs = {} if positional else {"tzinfo": zone}
        if positional:
            args.append(zone)
        expected = pendulum.DateTime.combine(*args, **kwargs)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            actual = DateTime.combine(*args, **kwargs)

        assert len(caught) == 1
        assert "Pendulum datetime member 'combine'" in str(caught[0].message)
        assert caught[0].filename == __file__
        assert actual == expected
        assert actual.tzinfo == expected.tzinfo

    @pytest.mark.parametrize("replacement", [None, 1])
    @pytest.mark.parametrize(
        "kind, field",
        [
            ("datetime", field)
            for field in (
                "year",
                "month",
                "day",
                "hour",
                "minute",
                "second",
                "microsecond",
                "fold",
            )
        ]
        + [("date", field) for field in ("year", "month", "day")]
        + [("time", field) for field in ("hour", "minute", "second", "microsecond")],
    )
    def test_replace_warns_for_none_and_stdlib_compatible_components(
        self, kind: str, field: str, replacement: int | None
    ):
        actual_value = create_datetime_instance(FIXED)
        native_value = pendulum.instance(FIXED)
        if kind != "datetime":
            actual_value = getattr(actual_value, kind)()
            native_value = getattr(native_value, kind)()
        expected = native_value.replace(**{field: replacement})
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'replace'"
        ) as caught:
            actual = actual_value.replace(**{field: replacement})
        assert len(caught) == 1
        assert caught[0].filename == __file__
        assert actual == expected
        if kind != "date":
            assert actual.tzinfo == expected.tzinfo
            assert actual.fold == expected.fold

    @pytest.mark.parametrize(
        "kind", ["datetime", "date", "time", "duration", "interval"]
    )
    def test_audited_shared_methods_warn_or_remain_quiet(self, kind: str):
        value = create_datetime_instance(FIXED)
        native = pendulum.instance(FIXED)
        date = datetime.date(2024, 6, 15)
        if kind == "datetime":
            stdlib = datetime.datetime
            cases = {
                "astimezone": ((datetime.UTC,), False),
                "combine": ((date, datetime.time(14, 30)), True),
                "date": ((), False),
                "fromordinal": ((date.toordinal(),), False),
                "fromtimestamp": ((0,), True),
                "now": ((), True),
                "replace": ((), True),
                "strptime": (("2024-06-15+0000", "%Y-%m-%d%z"), True),
                "time": ((), False),
                "today": ((), True),
                "utcfromtimestamp": ((0,), False),
                "utcnow": ((), True),
            }
        elif kind == "date":
            stdlib = datetime.date
            value, native = value.date(), native.date()
            cases = {
                "fromordinal": ((date.toordinal(),), False),
                "fromtimestamp": ((0,), False),
                "replace": ((), True),
                "today": ((), False),
            }
        elif kind == "time":
            stdlib = datetime.time
            value, native = value.time(), native.time()
            cases = {"replace": ((), True)}
        else:
            stdlib = datetime.timedelta
            if kind == "duration":
                value, native = Duration(days=1), pendulum.duration(days=1)
            else:
                value = value - create_datetime_instance(FIXED)
                native = native - pendulum.instance(FIXED)
            cases = {}

        # Require an explicit decision for every shared Python implementation.
        shared_overrides = set()
        for name in dir(stdlib):
            if name.startswith("_"):
                continue
            member = inspect.getattr_static(type(value), name)
            function = member.__func__ if isinstance(member, classmethod) else member
            if inspect.isfunction(function):
                shared_overrides.add(name)
        assert set(cases) == shared_overrides

        for member, (args, should_warn) in cases.items():
            with travel_to(FIXED), warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                expected = getattr(native, member)(*args)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.filterwarnings(
                        "always", "Pendulum datetime member", DeprecationWarning
                    )
                    actual = getattr(value, member)(*args)
            assert len(caught) == int(should_warn), member
            assert actual == expected, member
            if should_warn:
                assert f"Pendulum datetime member '{member}'" in str(caught[0].message)
                assert caught[0].filename == __file__

    @pytest.mark.parametrize("member", ["now", "fromtimestamp"])
    def test_constructor_default_timezone_warns(self, member: str):
        args = (0,) if member == "fromtimestamp" else ()
        with travel_to(FIXED):
            expected = getattr(pendulum.DateTime, member)(*args)
            with pytest.warns(
                DeprecationWarning, match=f"Pendulum datetime member '{member}'"
            ) as caught:
                actual = getattr(DateTime, member)(*args)
        assert caught[0].filename == __file__
        assert actual == expected
        assert actual.tzinfo == expected.tzinfo
        assert actual.tzinfo is not None

    @pytest.mark.parametrize(
        "member, args, should_warn",
        [
            ("today", (), True),
            ("utcnow", (), True),
            ("strptime", ("2024-06-15", "%Y-%m-%d"), True),
            ("strptime", ("2024-06-15+0000", "%Y-%m-%d%z"), True),
            ("fromordinal", (datetime.date(2024, 6, 15).toordinal(),), False),
            ("utcfromtimestamp", (0,), False),
        ],
    )
    def test_related_constructor_timezone_behavior(
        self, member: str, args: tuple[Any, ...], should_warn: bool
    ):
        with travel_to(FIXED), warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            expected = getattr(pendulum.DateTime, member)(*args)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", DeprecationWarning)
                actual = getattr(DateTime, member)(*args)
        notices = [
            warning
            for warning in caught
            if str(warning.message).startswith("Pendulum datetime member")
        ]
        assert len(notices) == int(should_warn)
        if should_warn:
            assert notices[0].filename == __file__
        assert actual == expected
        assert actual.tzinfo == expected.tzinfo

    @pytest.mark.parametrize("member", ["date", "time", "__sub__"])
    def test_overridden_stdlib_methods_keep_legacy_task_identity(self, member: str):
        value = create_datetime_instance(FIXED)
        legacy = PydanticDateTime.instance(FIXED)
        actual = task(getattr(value, member))
        expected = task(getattr(legacy, member))
        assert actual.task_key == expected.task_key
        assert actual.source_code == expected.source_code
        assert task_input_hash(
            TaskRunContext.model_construct(task=actual), {}
        ) == task_input_hash(TaskRunContext.model_construct(task=expected), {})

    @pytest.mark.parametrize("picklelib", ["pickle", "cloudpickle"])
    @pytest.mark.parametrize(
        "member, args, kwargs",
        [
            ("now", (), {"tz": datetime.timezone.utc}),
            ("today", (), {}),
            ("strptime", ("2024-06-15", "%Y-%m-%d"), {}),
            ("instance", (), {"dt": FIXED}),
        ],
    )
    def test_class_method_pickles_keep_existing_import_paths(
        self, picklelib: str, member: str, args: tuple[Any, ...], kwargs: dict[str, Any]
    ):
        class ExistingModuleReader(pickle.Unpickler):
            def find_class(self, module: str, name: str) -> Any:
                if module == "prefect.types._datetime_deprecations":
                    raise ImportError("Older readers do not have this module")
                return super().find_class(module, name)

        serializer = PickleSerializer(picklelib=picklelib)
        method = getattr(DateTime, member)
        serialized = serializer.dumps(method)
        restored = ExistingModuleReader(
            io.BytesIO(base64.decodebytes(serialized))
        ).load()
        with travel_to(FIXED), warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert restored(*args, **kwargs) == method(*args, **kwargs)

    def test_derived_times_keep_warning_behavior_and_stdlib_operations(self):
        value = create_datetime_instance(FIXED).time()
        expected = pendulum.instance(FIXED).time()
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            assert value == expected
            assert value.isoformat() == expected.isoformat()
            assert value.tzinfo is None
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'replace'"
        ):
            assert value.replace(minute=1) == expected.replace(minute=1)
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'add'"):
            later = value.add(hours=1)
        assert later == expected.add(hours=1)
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'subtract'"
        ):
            assert later.subtract(hours=1) == expected

    @pytest.mark.parametrize("time_only", [False, True])
    def test_explicit_pendulum_timezone_sentinel_warns(self, time_only: bool):
        value = create_datetime_instance(FIXED)
        if time_only:
            value = value.time()
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'replace'"
        ):
            replaced = value.replace(tzinfo=True)
        assert replaced == value
        assert replaced.tzinfo == value.tzinfo

    @pytest.mark.parametrize("picklelib", ["pickle", "cloudpickle"])
    @pytest.mark.parametrize("zone", [None, datetime.timezone.utc])
    @pytest.mark.parametrize("fold", [0, 1])
    def test_derived_time_pickle_supports_legacy_readers(
        self,
        monkeypatch: pytest.MonkeyPatch,
        picklelib: str,
        zone: datetime.tzinfo | None,
        fold: int,
    ):
        value = datetime.time.replace(
            create_datetime_instance(FIXED).time(), tzinfo=zone, fold=fold
        )
        serializer = PickleSerializer(picklelib=picklelib)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            serialized = serializer.dumps(value)
            restored = serializer.loads(serialized)
            with monkeypatch.context() as legacy:
                legacy.setattr(datetime_module, "DateTime", PydanticDateTime)
                legacy.delattr(datetime_module, "_Time", raising=False)
                old = serializer.loads(serialized)
        for result in (restored, old):
            assert result == value
            assert result.tzinfo == zone
            assert result.fold == fold
        assert type(old) is pendulum.Time
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'add'"):
            assert restored.add(hours=1) == pendulum.Time(
                value.hour, value.minute, value.second, value.microsecond, tzinfo=zone
            ).add(hours=1)

    def test_duration_schema_without_upstream_iso_serializer(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def legacy_schema(
            cls: type[PydanticDuration], source: Any, handler: GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            return core_schema.no_info_wrap_validator_function(
                cls._validate, core_schema.timedelta_schema()
            )

        monkeypatch.delattr(PydanticDuration, "to_iso8601_string", raising=False)
        monkeypatch.setattr(
            PydanticDuration, "__get_pydantic_core_schema__", classmethod(legacy_schema)
        )

        class Model(BaseModel):
            duration: Duration

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            value = Model(duration="P1D")
            assert value.duration == datetime.timedelta(days=1)
            assert value.model_dump_json() == '{"duration":"P1D"}'
        assert isinstance(value.duration, Duration)

    @pytest.mark.parametrize(
        "value",
        [
            datetime.timedelta.max,
            datetime.timedelta.min,
            datetime.timedelta(days=100000, microseconds=1),
            datetime.timedelta(days=-100000, microseconds=-1),
        ],
    )
    def test_duration_validation_preserves_exact_timedelta(
        self, value: datetime.timedelta
    ):
        result = TypeAdapter(Duration).validate_python(value)
        assert isinstance(result, Duration)
        assert result == value

    @pytest.mark.parametrize("text", ["P100000DT0.000001S", "P1Y2M100000DT0.000001S"])
    def test_parsed_duration_preserves_exact_value_and_calendar_units(self, text: str):
        expected = pendulum.parse(text)
        value = parse_datetime(text)
        assert isinstance(value, Duration)
        assert value == expected
        assert value.years == expected.years
        assert value.months == expected.months

    @pytest.mark.parametrize("picklelib", ["pickle", "cloudpickle"])
    @pytest.mark.parametrize("kind", ["datetime", "naive_datetime", "date"])
    @pytest.mark.parametrize("days", [-2, 0, 2])
    @pytest.mark.parametrize("absolute", [False, True])
    def test_interval_pickle_supports_legacy_readers(
        self, picklelib: str, kind: str, days: int, absolute: bool
    ):
        # Before this deprecation, the public names were Pydantic aliases and
        # the private _Interval class did not exist.
        legacy_types = {
            "DateTime": PydanticDateTime,
            "Date": PydanticDate,
            "Duration": PydanticDuration,
        }

        class LegacyDatetimeReader(pickle.Unpickler):
            def find_class(self, module: str, name: str) -> Any:
                if module == "prefect.types._datetime":
                    if name not in legacy_types:
                        raise AttributeError(f"Legacy datetime module has no {name!r}")
                    return legacy_types[name]
                return super().find_class(module, name)

        start = (
            create_datetime_instance(
                datetime.datetime(2024, 3, 9, 12, tzinfo=ZoneInfo("America/New_York"))
            )
            if kind != "date"
            else Date(2024, 3, 9)
        )
        if kind == "naive_datetime":
            start = start.replace(tzinfo=None)
        end = start + datetime.timedelta(days=days)
        expected = pendulum.interval(start, end, absolute=absolute)
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'diff'"):
            interval = start.diff(end, abs=absolute)

        serializer = PickleSerializer(picklelib=picklelib)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            serialized = serializer.dumps(interval)
            restored = serializer.loads(serialized)
            legacy = LegacyDatetimeReader(
                io.BytesIO(base64.decodebytes(serialized))
            ).load()

        for result in (restored, legacy):
            assert result == expected
            assert result.start == expected.start
            assert result.end == expected.end
            assert result.invert == expected.invert
            assert result.total_seconds() == expected.total_seconds()
        assert type(legacy) is pendulum.Interval
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'in_words'"
        ):
            assert restored.in_words(locale="en") == expected.in_words(locale="en")

    @pytest.mark.parametrize(
        "factory, member, kwargs, expected",
        [
            (
                lambda: create_datetime_instance(FIXED),
                "add",
                {"days": 1},
                FIXED + datetime.timedelta(days=1),
            ),
            (
                lambda: Date(2024, 6, 15),
                "add",
                {"days": 1},
                datetime.date(2024, 6, 16),
            ),
            (lambda: Duration(days=1), "in_words", {}, "1 day"),
            (
                lambda: DateTime(2024, 6, 15) - DateTime(2024, 6, 14),
                "in_words",
                {},
                "1 day",
            ),
            (lambda: DateTime, "instance", {"dt": FIXED}, FIXED),
        ],
    )
    def test_pendulum_methods_support_callback_registries(
        self,
        factory: Callable[[], Any],
        member: str,
        kwargs: dict[str, Any],
        expected: Any,
    ):
        value = factory()
        callback = getattr(value, member)
        repeated = getattr(value, member)
        assert callback == repeated
        assert len({callback, repeated}) == 1
        callbacks = [callback]
        callbacks.remove(repeated)
        assert callbacks == []
        assert callback.__self__ is value
        assert callback.__func__ is repeated.__func__

        callback_ref = weakref.WeakMethod(callback)
        del callback, repeated
        gc.collect()
        restored = callback_ref()
        assert restored == getattr(value, member)
        with pytest.warns(
            DeprecationWarning, match=f"Pendulum datetime member '{member}'"
        ):
            assert restored(**kwargs) == expected

    def test_pendulum_method_weak_reference_does_not_retain_receiver(self):
        value = create_datetime_instance(FIXED)
        callback_ref = weakref.WeakMethod(value.add)
        gc.collect()
        assert callback_ref() is not None

        del value
        gc.collect()
        assert callback_ref() is None

    @pytest.mark.parametrize(
        "cls, native",
        [(DateTime, lambda: pendulum.DateTime), (Date, lambda: pendulum.Date)],
    )
    def test_pendulum_method_aliases_keep_equality_and_pickling(
        self, cls: type, native: Callable[[], type]
    ):
        value = cls(2024, 6, 15)
        expected = native()(2024, 6, 15)
        assert (value.is_birthday == value.is_anniversary) == (
            expected.is_birthday == expected.is_anniversary
        )
        restored = pickle.loads(pickle.dumps(value.is_birthday))
        assert restored.__func__ is value.is_birthday.__func__
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'is_anniversary'"
        ):
            assert restored(datetime.date(2020, 6, 15))

    def test_pendulum_method_can_be_called_unbound(self):
        value = create_datetime_instance(FIXED)
        restored = pickle.loads(pickle.dumps(DateTime.add))
        assert restored is DateTime.add
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'add'"):
            assert restored(value, days=1) == FIXED + datetime.timedelta(days=1)

    def test_user_decorator_around_pendulum_method_keeps_its_own_task_key(self):
        method = create_datetime_instance(FIXED).add

        @wraps(method)
        def decorated(**kwargs: Any) -> datetime.datetime:
            return method(**kwargs)

        assert task(decorated).task_key != task(method).task_key

    @pytest.mark.parametrize("name", ["EPOCH", "min", "max"])
    def test_datetime_constants_retain_warning_behavior(self, name: str):
        expected = getattr(pendulum.DateTime, name)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            value = getattr(DateTime, name)
            restored = pickle.loads(pickle.dumps(value))
            assert value == restored == expected
            assert value.isoformat() == expected.isoformat()
            assert value.tzinfo == restored.tzinfo == expected.tzinfo

        for constant in (value, restored):
            with pytest.warns(
                DeprecationWarning, match="Pendulum datetime member 'add'"
            ):
                assert constant.add(days=0) == expected
            assert isinstance(constant, DateTime)
        assert not isinstance(expected, DateTime)

    @pytest.mark.parametrize("name", ["min", "max", "resolution"])
    def test_duration_constants_retain_warning_behavior(self, name: str):
        expected = getattr(pendulum.Duration, name)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            value = getattr(Duration, name)
            restored = pickle.loads(pickle.dumps(value))
            assert value == restored == expected
            assert value.total_seconds() == expected.total_seconds()

        for constant in (value, restored):
            with pytest.warns(
                DeprecationWarning, match="Pendulum datetime member 'in_words'"
            ):
                assert constant.in_words() == expected.in_words()
            assert isinstance(constant, Duration)
        assert not isinstance(expected, Duration)

    def test_stdlib_constants_remain_unchanged(self):
        assert Date.min is datetime.date.min
        assert Date.max is datetime.date.max
        assert Date.resolution is datetime.date.resolution
        assert DateTime.resolution is datetime.datetime.resolution

    @pytest.mark.parametrize(
        "factory, member, kwargs",
        [
            (lambda: create_datetime_instance(FIXED).date(), "add", {"days": 1}),
            (lambda: create_datetime_instance(FIXED).time(), "add", {"hours": 1}),
            (lambda: create_datetime_instance(FIXED).time().min, "add", {"hours": 1}),
            (
                lambda: create_datetime_instance(FIXED).time().max,
                "subtract",
                {"hours": 1},
            ),
            (lambda: create_datetime_instance(FIXED).time().resolution, "in_words", {}),
            (
                lambda: (
                    create_datetime_instance(FIXED)
                    - create_datetime_instance(FIXED - datetime.timedelta(days=1))
                ),
                "in_words",
                {},
            ),
            (lambda: Date(2024, 6, 15) - Date(2024, 6, 14), "in_words", {}),
            (
                lambda: DateTime(2024, 6, 15) - datetime.datetime(2024, 6, 14),
                "in_words",
                {},
            ),
            (
                lambda: datetime.datetime(2024, 6, 15) - DateTime(2024, 6, 14),
                "in_words",
                {},
            ),
        ],
    )
    def test_derived_values_warn_on_pendulum_members(
        self, factory: Callable[[], Any], member: str, kwargs: dict[str, Any]
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            value = factory()
            pickle.loads(pickle.dumps(value))

        with pytest.warns(
            DeprecationWarning, match=f"Pendulum datetime member '{member}'"
        ):
            getattr(value, member)(**kwargs)

    @pytest.mark.parametrize("zone", ["UTC", "America/New_York", "Europe/Paris"])
    @pytest.mark.parametrize(
        "factory",
        [
            lambda: create_datetime_instance(FIXED),
            lambda: DateTime(2024, 6, 15, 14, 30),
            lambda: DateTime(
                2024, 3, 10, 1, 30, tzinfo=pendulum.timezone("America/New_York")
            ),
            lambda: DateTime(
                2024, 11, 3, 1, 30, tzinfo=pendulum.timezone("America/New_York"), fold=1
            ),
        ],
    )
    def test_timezone_conversion_preserves_pendulum_behavior(
        self, factory: Callable[[], DateTime], zone: str
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            value = factory()
            expected = pendulum.DateTime.instance(value, tz=value.tzinfo).astimezone(
                ZoneInfo(zone)
            )
            actual = value.astimezone(ZoneInfo(zone))

        assert actual == expected
        assert actual.tzinfo == expected.tzinfo
        assert actual.utcoffset() == expected.utcoffset()
        assert actual.fold == expected.fold

    @pytest.mark.parametrize("absolute", [False, True])
    def test_derived_intervals_preserve_endpoints_and_range(self, absolute: bool):
        start = create_datetime_instance(FIXED)
        end = create_datetime_instance(FIXED - datetime.timedelta(days=2))
        expected = pendulum.interval(start, end, absolute=absolute)
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'diff'"):
            interval = start.diff(end, abs=absolute)

        assert isinstance(interval, pendulum.Interval)
        assert interval.start == expected.start
        assert interval.end == expected.end
        assert interval.total_seconds() == expected.total_seconds()
        assert pickle.loads(pickle.dumps(interval)) == expected
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'range'"):
            assert list(interval.range("days")) == list(expected.range("days"))

    @pytest.mark.parametrize(
        "member, kwargs",
        [
            ("instance", {"dt": FIXED}),
            ("create", {"year": 2024, "month": 6, "day": 15}),
        ],
    )
    def test_pendulum_class_methods_warn(self, member: str, kwargs: dict[str, Any]):
        restored = pickle.loads(pickle.dumps(getattr(DateTime, member)))
        with pytest.warns(
            DeprecationWarning, match=f"Pendulum datetime member '{member}'"
        ):
            value = restored(**kwargs)
        assert isinstance(value, DateTime)

    def test_duration_iso_method_warns(self):
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'to_iso8601_string'"
        ):
            assert Duration(months=1).to_iso8601_string() == "P1M"

    @pytest.mark.parametrize("text", ["P1D", "2024-06-15/2024-06-17"])
    def test_parser_preserves_non_datetime_values(self, text: str):
        expected = pendulum.parse(text)
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            value = parse_datetime(text)

        assert isinstance(value, type(expected))
        assert value == expected
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'in_words'"
        ):
            value.in_words()

    def test_pendulum_method_task_keys_preserve_method_identity(self):
        dt = create_datetime_instance(FIXED)
        methods = [
            dt.add,
            dt.subtract,
            dt.in_tz,
            Date(2024, 6, 15).add,
            Date(2024, 6, 15).replace,
            Duration(days=1).in_words,
            DateTime.instance,
            DateTime.create,
            DateTime.now,
            DateTime.fromtimestamp,
            DateTime.combine,
            dt.replace,
            dt.time,
            dt.time().add,
            dt.time().replace,
        ]
        tasks = [task(method) for method in methods]
        assert len({wrapped.task_key for wrapped in tasks}) == len(tasks)
        for wrapped, method in zip(tasks, methods):
            original = task(method.__wrapped__)
            assert wrapped.task_key == original.task_key
            assert wrapped.source_code == original.source_code
            assert task_input_hash(
                TaskRunContext.model_construct(task=wrapped), {"days": 1}
            ) == task_input_hash(
                TaskRunContext.model_construct(task=original), {"days": 1}
            )

    @pytest.mark.parametrize(
        "factory",
        [
            lambda: now("UTC"),
            lambda: from_timestamp(0),
            lambda: parse_datetime("2024-W24-6T14:30:45"),
            lambda: create_datetime_instance(FIXED),
            lambda: start_of_day(FIXED),
            lambda: end_of_period(FIXED, "day"),
            lambda: end_of_period(FIXED, "month"),
            lambda: end_of_period(FIXED, "year"),
            lambda: in_local_tz(FIXED),
        ],
    )
    def test_helpers_retain_pendulum_methods(
        self, factory: Callable[[], datetime.datetime]
    ):
        value = factory()
        assert isinstance(value, pendulum.DateTime)
        assert value.add(days=1) > value
        assert value.in_tz("UTC").utcoffset() == datetime.timedelta(0)
        assert isinstance(value.to_iso8601_string(), str)

    def test_human_friendly_diff_preserves_pendulum_wording(self):
        assert (
            human_friendly_diff(FIXED, FIXED + datetime.timedelta(days=1))
            == "1 day before"
        )

    @pytest.mark.parametrize("input_type", ["strings", "pendulum"])
    @pytest.mark.parametrize(
        "duration, years, months",
        [("P1M2DT3H", 0, 1), ("P1Y2M9DT3H4M5.123456S", 1, 2)],
    )
    def test_pydantic_types_preserve_calendar_duration_and_json(
        self, input_type: str, duration: str, years: int, months: int
    ):
        class Model(BaseModel):
            timestamp: DateTime
            date: Date
            duration: Duration

        inputs = {
            "strings": {
                "timestamp": "2024-06-15T14:30:45Z",
                "date": "2024-06-15",
                "duration": duration,
            },
            "pendulum": {
                "timestamp": pendulum.datetime(2024, 6, 15, 14, 30, 45),
                "date": pendulum.date(2024, 6, 15),
                "duration": pendulum.parse(duration, exact=True),
            },
        }

        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            value = Model(**inputs[input_type])
            serialized = value.model_dump_json()

        assert isinstance(value.timestamp, DateTime)
        assert isinstance(value.timestamp, pendulum.DateTime)
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'in_tz'"):
            assert value.timestamp.in_tz("America/New_York").hour == 10
        assert isinstance(value.date, Date)
        assert isinstance(value.date, pendulum.Date)
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'add'"):
            assert value.date.add(days=1).day == 16
        assert isinstance(value.duration, Duration)
        assert isinstance(value.duration, pendulum.Duration)
        assert value.duration.years == years
        assert value.duration.months == months
        with pytest.warns(
            DeprecationWarning, match="Pendulum datetime member 'in_words'"
        ):
            value.duration.in_words()
        assert serialized == (
            '{"timestamp":"2024-06-15T14:30:45Z","date":"2024-06-15",'
            f'"duration":"{duration}"}}'
        )

    def test_api_model_timestamps_warn_on_pendulum_methods(self):
        run = FlowRun.model_validate(
            {
                "flow_id": "00000000-0000-0000-0000-000000000001",
                "created": "2024-06-15T14:30:45Z",
            }
        )

        assert isinstance(run.created, DateTime)
        with pytest.warns(DeprecationWarning, match="Pendulum datetime member 'add'"):
            assert run.created.add(days=1).day == 16

    def test_direct_construction_and_frozen_pendulum_clock(self):
        value = DateTime.instance(FIXED)
        assert value.in_tz("UTC").hour == 18
        assert value.naive().tzinfo is None
        with travel_to(FIXED):
            assert DateTime.now("UTC") == FIXED


class TestPatchedClock:
    @pytest.mark.parametrize("clock_fixture", ["frozen_time", "advance_time"])
    def test_patched_now_stays_aware_under_arithmetic(
        self, request: pytest.FixtureRequest, clock_fixture: str
    ):
        request.getfixturevalue(clock_fixture)
        current = prefect.types._datetime.now("UTC")

        earlier = current - datetime.timedelta(minutes=1)

        assert earlier.tzinfo is not None
        assert earlier == datetime.datetime.fromtimestamp(
            current.timestamp(), datetime.timezone.utc
        ) - datetime.timedelta(minutes=1)
