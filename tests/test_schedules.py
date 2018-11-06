from datetime import datetime, time, timedelta

import pytest

from prefect import schedules, __version__

START_DATE = datetime(2018, 1, 1)
NOW = datetime.utcnow()
TODAY = datetime.combine(NOW.date(), time())
DATES = [
    TODAY + timedelta(days=1),
    TODAY + timedelta(days=2),
    TODAY + timedelta(days=3),
    TODAY + timedelta(days=4),
    TODAY + timedelta(days=5),
    TODAY + timedelta(days=6),
]


def test_create_base_schedule():
    assert schedules.Schedule()


def test_base_schedule_next_no_implemented():
    s = schedules.Schedule()
    with pytest.raises(NotImplementedError):
        s.next(1)


def test_create_interval_schedule():
    assert schedules.IntervalSchedule(start_date=START_DATE, interval=timedelta(days=1))


def test_interval_schedule_interval_must_be_positive():
    with pytest.raises(ValueError):
        schedules.IntervalSchedule(START_DATE, interval=timedelta(hours=-1))


def test_interval_schedule_next_n():
    s = schedules.IntervalSchedule(START_DATE, timedelta(days=1))
    assert s.next(3) == DATES[:3]


def test_interval_schedule_next_n_with_on_or_after_argument():
    s = schedules.IntervalSchedule(START_DATE, timedelta(days=1))
    assert s.next(3, on_or_after=TODAY + timedelta(days=4)) == DATES[3:]


def test_create_cron_schedule():
    assert schedules.CronSchedule("* * * * *")


def test_create_cron_schedule_with_invalid_cron_string_raises_error():
    with pytest.raises(Exception):
        schedules.CronSchedule("*")
    with pytest.raises(Exception):
        schedules.CronSchedule("hello world")
    with pytest.raises(Exception):
        schedules.CronSchedule(1)


def test_cron_schedule_next_n():
    every_day = "0 0 * * *"
    s = schedules.CronSchedule(every_day)
    assert s.next(3) == DATES[:3]


def test_cron_schedule_next_n_with_on_or_after_argument():
    every_day = "0 0 * * *"
    s = schedules.CronSchedule(every_day)
    assert s.next(3, on_or_after=TODAY + timedelta(days=4)) == DATES[3:]


class TestSerialization:
    def test_serialize_cron_schedule(self):
        schedule = schedules.CronSchedule("0 0 * * *")
        assert schedule.serialize() == {
            "type": "CronSchedule",
            "cron": "0 0 * * *",
            "__version__": __version__,
        }

    def test_serialize_interval_schedule(self):
        schedule = schedules.IntervalSchedule(
            interval=timedelta(hours=1), start_date=START_DATE
        )
        assert schedule.serialize() == {
            "type": "IntervalSchedule",
            "start_date": "2018-01-01T00:00:00+00:00",
            "interval": 3600,
            "__version__": __version__,
        }
