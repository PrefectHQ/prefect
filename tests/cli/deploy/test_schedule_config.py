"""Tests for schedule configuration in deployment YAML."""

import pytest

from prefect.cli.deploy._models import RawScheduleConfig
from prefect.cli.deploy._schedules import _schedule_config_to_deployment_schedule
from prefect.client.schemas.schedules import CronSchedule, IntervalSchedule


def test_cron_schedule_with_day_or_and_active():
    """Test that cron schedule with both day_or and active fields validates.

    Regression test for issue #19117 where using day_or and active together
    would fail with "Extra inputs are not permitted" error.
    """
    # Test RawScheduleConfig model accepts both fields
    schedule = RawScheduleConfig(
        cron="0 3 * * *",
        timezone="UTC",
        active=False,
        day_or=True,
    )
    assert schedule.cron == "0 3 * * *"
    assert schedule.active is False
    assert schedule.day_or is True

    # Test that conversion to CronSchedule passes day_or through
    schedule_config = {
        "cron": "0 3 * * *",
        "timezone": "UTC",
        "active": False,
        "day_or": True,
    }

    result = _schedule_config_to_deployment_schedule(schedule_config)

    assert result["active"] is False
    schedule = result["schedule"]
    assert isinstance(schedule, CronSchedule)
    assert schedule.day_or is True


class TestIntervalScheduleFormats:
    """Test various interval formats accepted in prefect.yaml."""

    @pytest.mark.parametrize(
        "interval_value,expected_seconds",
        [
            (600, 600),  # integer seconds
            (600.5, 600.5),  # float seconds
            ("PT10M", 600),  # ISO 8601: 10 minutes
            ("PT1H30M", 5400),  # ISO 8601: 1 hour 30 minutes
            ("PT1H", 3600),  # ISO 8601: 1 hour
            ("P1D", 86400),  # ISO 8601: 1 day
            ("1:30:00", 5400),  # time format: HH:MM:SS
            ("00:10:00", 600),  # time format: 10 minutes
        ],
    )
    def test_interval_schedule_accepts_various_formats(
        self, interval_value, expected_seconds
    ):
        """Test that interval schedules accept integers, floats, ISO 8601 durations,
        and time format strings in prefect.yaml.

        The underlying IntervalSchedule pydantic model accepts these formats via
        pydantic's timedelta parsing, so the CLI YAML model should too.
        """
        # Test RawScheduleConfig model accepts the format
        schedule = RawScheduleConfig(
            interval=interval_value,
            timezone="UTC",
            active=False,
        )
        assert schedule.interval is not None

        # Test conversion to IntervalSchedule works
        schedule_config = {
            "interval": interval_value,
            "timezone": "UTC",
            "active": False,
        }

        result = _schedule_config_to_deployment_schedule(schedule_config)

        assert result["active"] is False
        schedule = result["schedule"]
        assert isinstance(schedule, IntervalSchedule)
        assert schedule.interval.total_seconds() == expected_seconds
