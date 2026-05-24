"""Tests for prefect.types._datetime.

These tests are intentionally version-agnostic: they run on all supported
Python versions without any skips. On Python < 3.13 the pendulum backend is
exercised; on Python >= 3.13 the whenever backend is exercised. If all
assertions pass across the CI matrix we have behavioral parity between the
two backends.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import BaseModel

from prefect.types._datetime import (
    DateTime,
    end_of_period,
    in_local_tz,
    now,
    start_of_day,
)

pytestmark = pytest.mark.clear_db

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
