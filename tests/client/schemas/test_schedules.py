import datetime
from itertools import combinations

import pytest

from prefect.client.schemas.actions import (
    DeploymentFlowRunCreate,
    DeploymentScheduleCreate,
)
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
    construct_schedule,
)
from prefect.types import DateTime
from prefect.types._datetime import now


class TestConstructSchedule:
    def test_construct_interval_schedule(self):
        interval = 300  # 5 minutes
        result = construct_schedule(interval=interval)
        assert isinstance(result, IntervalSchedule)
        assert result.interval == datetime.timedelta(seconds=interval)

    def test_construct_cron_schedule(self):
        cron_string = "0 0 * * *"
        result = construct_schedule(cron=cron_string)
        assert isinstance(result, CronSchedule)
        assert result.cron == cron_string

    def test_construct_rrule_schedule(self):
        rrule_string = "FREQ=DAILY;COUNT=2"
        result = construct_schedule(rrule=rrule_string)
        assert isinstance(result, RRuleSchedule)
        assert result.rrule == rrule_string

    @pytest.mark.parametrize(
        "kwargs",
        [
            {**d1, **d2}
            for d1, d2 in combinations(
                [
                    {"interval": 3600},
                    {"cron": "* * * * *"},
                    {"rrule": "FREQ=MINUTELY"},
                ],
                2,
            )
        ],
    )
    def test_multiple_schedules_error(self, kwargs):
        with pytest.raises(
            ValueError, match="Only one of interval, cron, or rrule can be provided."
        ):
            construct_schedule(**kwargs)

    def test_anchor_date_without_interval_error(self):
        with pytest.raises(
            ValueError,
            match="An anchor date can only be provided with an interval schedule",
        ):
            construct_schedule(anchor_date="2023-01-01")

    def test_timezone_without_schedule_error(self):
        with pytest.raises(
            ValueError,
            match="A timezone can only be provided with interval, cron, or rrule",
        ):
            construct_schedule(timezone="UTC")

    def test_no_schedule_error(self):
        with pytest.raises(
            ValueError, match="Either interval, cron, or rrule must be provided"
        ):
            construct_schedule()

    def test_timedelta_interval_schedule(self):
        interval = datetime.timedelta(minutes=5)
        result = construct_schedule(interval=interval)
        assert isinstance(result, IntervalSchedule)
        assert result.interval == interval

    def test_datetime_anchor_date(self):
        anchor = now()
        result = construct_schedule(interval=300, anchor_date=anchor)
        assert result == IntervalSchedule(
            interval=datetime.timedelta(seconds=300), anchor_date=anchor
        )

    def test_string_anchor_date(self):
        anchor = "2023-01-01T00:00:00+00:00"
        result = construct_schedule(interval=300, anchor_date=anchor)
        assert result == IntervalSchedule(
            interval=datetime.timedelta(seconds=300),
            anchor_date=DateTime.fromisoformat(anchor),
        )

    @pytest.mark.parametrize(
        "value",
        [
            "not even almost a boolean",
            "{{ to.be.templated }}",
        ],
    )
    def test_invalid_active_value(self, value: str):
        with pytest.raises(
            ValueError, match="active must be able to be parsed as a boolean"
        ):
            schedule = IntervalSchedule(interval=datetime.timedelta(seconds=300))
            DeploymentScheduleCreate(active=value, schedule=schedule)

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("True", True),
            ("False", False),
            ("true", True),
            ("false", False),
            ("TRUE", True),
            ("FALSE", False),
            ("1", True),
            ("0", False),
        ],
    )
    def test_parsable_active_value(self, value: str, expected: bool):
        schedule = IntervalSchedule(interval=datetime.timedelta(seconds=300))
        assert (
            DeploymentScheduleCreate(active=value, schedule=schedule).active == expected
        )


class TestDeploymentFlowRunCreate:
    """Test DeploymentFlowRunCreate schema serialization"""

    def test_datetime_parameter_serialization(self):
        """datetime.datetime should be serialized as ISO string"""
        dt = datetime.datetime(2025, 10, 24, 11, 5, 30, 123456)

        flow_run_create = DeploymentFlowRunCreate(parameters={"dt": dt})
        dumped = flow_run_create.model_dump(mode="json")

        # Should be ISO string, not timestamp float
        assert isinstance(dumped["parameters"]["dt"], str)
        assert dumped["parameters"]["dt"] == "2025-10-24T11:05:30.123456"

    def test_date_parameter_serialization(self):
        """datetime.date should be serialized as ISO string"""
        date = datetime.date(2025, 10, 24)

        flow_run_create = DeploymentFlowRunCreate(parameters={"date": date})
        dumped = flow_run_create.model_dump(mode="json")

        # Should be ISO string, not timestamp float
        assert isinstance(dumped["parameters"]["date"], str)
        assert dumped["parameters"]["date"] == "2025-10-24"

    def test_nested_datetime_parameter_serialization(self):
        """Nested datetime objects should also be serialized"""
        dt = datetime.datetime(2025, 10, 24, 11, 5, 30)
        date = datetime.date(2025, 10, 24)

        flow_run_create = DeploymentFlowRunCreate(
            parameters={"config": {"start_time": dt, "end_date": date, "count": 42}}
        )
        dumped = flow_run_create.model_dump(mode="json")

        # Nested datetime should be ISO string
        assert isinstance(dumped["parameters"]["config"]["start_time"], str)
        assert dumped["parameters"]["config"]["start_time"] == "2025-10-24T11:05:30"
        assert isinstance(dumped["parameters"]["config"]["end_date"], str)
        assert dumped["parameters"]["config"]["end_date"] == "2025-10-24"
        # Other values should be unchanged
        assert dumped["parameters"]["config"]["count"] == 42

    def test_list_datetime_parameter_serialization(self):
        """List of datetime objects should be serialized"""
        dates = [
            datetime.date(2025, 10, 24),
            datetime.date(2025, 10, 25),
        ]

        flow_run_create = DeploymentFlowRunCreate(parameters={"dates": dates})
        dumped = flow_run_create.model_dump(mode="json")

        # List items should be ISO strings
        assert isinstance(dumped["parameters"]["dates"], list)
        assert len(dumped["parameters"]["dates"]) == 2
        assert dumped["parameters"]["dates"][0] == "2025-10-24"
        assert dumped["parameters"]["dates"][1] == "2025-10-25"
