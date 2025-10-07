"""Tests for schedule configuration in deployment YAML."""

from prefect.cli.deploy._models import RawScheduleConfig
from prefect.cli.deploy._schedules import _schedule_config_to_deployment_schedule
from prefect.client.schemas.schedules import CronSchedule


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
