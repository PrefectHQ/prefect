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

from prefect.types._datetime import end_of_period, in_local_tz, now, start_of_day

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
