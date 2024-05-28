import datetime
from itertools import combinations

import pytest
from pydantic_extra_types.pendulum_dt import DateTime

from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
    construct_schedule,
)


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
        anchor = DateTime.now()
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
