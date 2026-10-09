"""Tests for prefect.types._datetime.

These tests exercise the `whenever`-backed datetime helpers used across all
supported Python versions.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel

from prefect.types._datetime import (
    DateTime,
    end_of_period,
    from_timestamp,
    in_local_tz,
    now,
    start_of_day,
    travel_to,
)

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

    @pytest.mark.parametrize(
        "tz",
        [
            ZoneInfo("UTC"),
            ZoneInfo("America/New_York"),
            datetime.UTC,
            datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
        ],
    )
    def test_accepts_tzinfo_objects(self, tz: datetime.tzinfo):
        result = now(tz)

        assert result.tzinfo is not None
        assert result.utcoffset() == datetime.datetime.now(tz).utcoffset()


class TestFromTimestamp:
    @pytest.mark.parametrize(
        "tz",
        [
            "UTC",
            ZoneInfo("UTC"),
            datetime.UTC,
            datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
        ],
    )
    def test_accepts_string_and_tzinfo(self, tz):
        result = from_timestamp(0, tz)

        assert result.tzinfo is not None
        assert result.astimezone(ZoneInfo("UTC")) == datetime.datetime(
            1970, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC")
        )


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

    def test_fixed_offset_tzinfo(self):
        fixed = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        result = start_of_day(datetime.datetime(2024, 6, 15, 14, 30, 45, tzinfo=fixed))

        assert result == datetime.datetime(2024, 6, 15, tzinfo=fixed)

    def test_timezone_utc(self):
        result = start_of_day(
            datetime.datetime(2024, 6, 15, 14, 30, 45, tzinfo=datetime.UTC)
        )

        assert result == datetime.datetime(2024, 6, 15, tzinfo=datetime.UTC)


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
        with pytest.raises(ValueError, match="Invalid period"):
            end_of_period(FIXED, "century")

    @pytest.mark.parametrize(
        "period, expected",
        [
            (
                "day",
                datetime.datetime(2024, 6, 15, 23, 59, 59, 999999),
            ),
            (
                # June 15 (Sat) → end of ISO week = Sunday June 16
                "week",
                datetime.datetime(2024, 6, 16, 23, 59, 59, 999999),
            ),
        ],
    )
    def test_fixed_offset_tzinfo(self, period: str, expected: datetime.datetime):
        fixed = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        result = end_of_period(
            datetime.datetime(2024, 6, 15, 14, 30, 45, tzinfo=fixed), period
        )

        assert result == expected.replace(tzinfo=fixed)


class TestTravelTo:
    def test_freezes_now_for_all_callers(self):
        """`travel_to` freezes `whenever`'s clock globally, so even modules
        that bound `now` via `from ... import now` observe the frozen time —
        matching pendulum's `travel_to(freeze=True)` semantics."""
        frozen = datetime.datetime(2030, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        with travel_to(frozen):
            assert now("UTC") == frozen
            assert now("America/New_York").astimezone(ZoneInfo("UTC")) == frozen

        assert now("UTC") != frozen
        assert (
            abs((now("UTC") - datetime.datetime.now(ZoneInfo("UTC"))).total_seconds())
            < 60
        )


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

    It is a `datetime.datetime` subclass with a Pydantic schema that enforces
    tz-awareness — a naive input must come out tz-aware. See #21949.
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

    def test_result_is_a_datetime_alias_instance(self):
        class Model(BaseModel):
            when: DateTime

        result = Model(when="2024-06-15T14:30:45Z").when
        assert isinstance(result, DateTime)
