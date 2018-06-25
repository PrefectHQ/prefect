import pytest
from datetime import datetime, timedelta, time
from prefect import schedules

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
        s.next_n(1)
    with pytest.raises(NotImplementedError):
        s.next()


def test_create_no_schedule():
    assert schedules.NoSchedule()


def test_no_schedule_returns_no_dates():
    s = schedules.NoSchedule()
    assert s.next_n(1) == []
    assert s.next() is None


def test_create_interval_schedule():
    assert schedules.IntervalSchedule(start_date=START_DATE, interval=timedelta(days=1))


def test_interval_schedule_interval_must_be_positive():
    with pytest.raises(ValueError):
        schedules.IntervalSchedule(START_DATE, interval=timedelta(hours=-1))


def test_interval_schedule_next():
    s = schedules.IntervalSchedule(START_DATE, timedelta(days=1))
    assert s.next() == TODAY + timedelta(days=1)


def test_interval_schedule_next_n():
    s = schedules.IntervalSchedule(START_DATE, timedelta(days=1))
    assert s.next_n(3) == DATES[:3]


def test_interval_schedule_next_n_with_on_or_after_argument():
    s = schedules.IntervalSchedule(START_DATE, timedelta(days=1))
    assert s.next_n(3, on_or_after=TODAY + timedelta(days=4)) == DATES[3:]


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
    assert s.next_n(3) == DATES[:3]


def test_cron_schedule_next_n_with_on_or_after_argument():
    every_day = "0 0 * * *"
    s = schedules.CronSchedule(every_day)
    assert s.next_n(3, on_or_after=TODAY + timedelta(days=4)) == DATES[3:]


def test_cron_schedule_next():
    every_day = "0 0 * * *"
    s = schedules.CronSchedule(every_day)
    assert s.next() == DATES[0]


def test_create_date_schedule():
    s = schedules.DateSchedule(DATES)
    assert s.dates == DATES


def test_date_schedule_next_n():
    s = schedules.DateSchedule(DATES)
    assert s.next_n(3) == DATES[:3]


def test_date_schedule_next_n_with_on_or_after_argument():
    s = schedules.DateSchedule(DATES)
    assert s.next_n(3, on_or_after=TODAY + timedelta(days=4)) == DATES[3:]


def test_date_schedule_after_last_date_returns_empty_list():
    s = schedules.DateSchedule(DATES)
    assert s.next_n(3, on_or_after=TODAY + timedelta(days=100)) == []
