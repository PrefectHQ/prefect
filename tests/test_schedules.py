import datetime

import pytest

from prefect.schedules import Cron, Interval, RRule, Schedule


class TestSchedule:
    def test_schedule_requires_single_schedule_type(self):
        with pytest.raises(ValueError, match="Only one schedule type can be defined"):
            Schedule(interval=datetime.timedelta(days=1), cron="0 0 * * *")

        with pytest.raises(ValueError, match="Only one schedule type can be defined"):
            Schedule(cron="0 0 * * *", rrule="RRULE:FREQ=DAILY")

    def test_schedule_validates_cron_string(self):
        with pytest.raises(ValueError, match="Invalid cron string"):
            Schedule(cron="invalid")

    def test_schedule_validates_rrule_string(self):
        with pytest.raises(ValueError, match="Invalid RRule string"):
            Schedule(rrule="invalid")

    def test_schedule_default_values(self):
        schedule = Schedule()
        assert schedule.interval is None
        assert schedule.cron is None
        assert schedule.rrule is None
        assert schedule.timezone is None
        assert isinstance(schedule.anchor_date, datetime.datetime)
        assert schedule.day_or is False
        assert schedule.active is True
        assert schedule.parameters == {}


class TestCronSchedule:
    def test_cron_schedule_creation(self):
        schedule = Cron("0 0 * * *")
        assert schedule.cron == "0 0 * * *"
        assert schedule.timezone is None
        assert schedule.day_or is False
        assert schedule.active is True
        assert schedule.parameters == {}

    def test_cron_schedule_with_all_parameters(self):
        params = {"key": "value"}
        schedule = Cron(
            "0 0 * * *",
            timezone="America/New_York",
            day_or=True,
            active=False,
            parameters=params,
        )
        assert schedule.cron == "0 0 * * *"
        assert schedule.timezone == "America/New_York"
        assert schedule.day_or is True
        assert schedule.active is False
        assert schedule.parameters == params


class TestIntervalSchedule:
    def test_interval_schedule_with_timedelta(self):
        interval = datetime.timedelta(days=1)
        schedule = Interval(interval)
        assert schedule.interval == interval
        assert isinstance(schedule.anchor_date, datetime.datetime)
        assert schedule.timezone is None
        assert schedule.active is True
        assert schedule.parameters == {}

    def test_interval_schedule_with_seconds(self):
        schedule = Interval(3600)
        assert schedule.interval == datetime.timedelta(seconds=3600)

    def test_interval_schedule_with_float_seconds(self):
        schedule = Interval(1.5)
        assert schedule.interval == datetime.timedelta(seconds=1.5)

    def test_interval_schedule_with_custom_anchor(self):
        anchor = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
        schedule = Interval(
            datetime.timedelta(hours=1), anchor_date=anchor, timezone="UTC"
        )
        assert schedule.anchor_date == anchor
        assert schedule.timezone == "UTC"


class TestRRuleSchedule:
    def test_rrule_schedule_creation(self):
        rrule = "RRULE:FREQ=DAILY;INTERVAL=1"
        schedule = RRule(rrule)
        assert schedule.rrule == rrule
        assert schedule.timezone is None
        assert schedule.active is True
        assert schedule.parameters == {}

    def test_rrule_schedule_with_all_parameters(self):
        rrule = "RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR"
        params = {"key": "value"}
        schedule = RRule(
            rrule, timezone="Europe/London", active=False, parameters=params
        )
        assert schedule.rrule == rrule
        assert schedule.timezone == "Europe/London"
        assert schedule.active is False
        assert schedule.parameters == params
