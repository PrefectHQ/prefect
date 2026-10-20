"""Tests for schedule configuration in deployment YAML."""

from pathlib import Path

import pytest
import yaml
from rich.console import Console

from prefect.cli.deploy._config import _load_deploy_configs_and_actions
from prefect.cli.deploy._models import RawScheduleConfig
from prefect.cli.deploy._schedules import _schedule_config_to_deployment_schedule
from prefect.client.schemas.schedules import CronSchedule, IntervalSchedule
from prefect.deployments.base import _format_deployment_for_saving_to_prefect_file


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
        "interval", ["P1M", "P1Y", "PT48H", "P1M1W", "PT0.0000015S", "P1D", "PT42S"]
    )
    def test_saved_interval_survives_yaml_reload(self, tmp_path: Path, interval: str):
        schedule = IntervalSchedule(
            interval=interval, anchor_date="2024-01-31T12:00:00Z", timezone="UTC"
        )
        saved = _format_deployment_for_saving_to_prefect_file(
            {
                "name": "calendar",
                "parameter_openapi_schema": {},
                "schedules": [{"schedule": schedule, "active": True}],
            }
        )
        prefect_file = tmp_path / "prefect.yaml"
        prefect_file.write_text(yaml.safe_dump({"deployments": [saved]}))

        configs, _ = _load_deploy_configs_and_actions(
            prefect_file=prefect_file, console=Console()
        )
        restored = _schedule_config_to_deployment_schedule(configs[0]["schedules"][0])

        assert restored["active"] is True
        assert restored["schedule"].model_dump(mode="json") == schedule.model_dump(
            mode="json"
        )

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
