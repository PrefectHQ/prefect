import pendulum
from datetime import time, timedelta

import pytest

from prefect import schedules, __version__

START_DATE = pendulum.datetime(2018, 1, 1)
DATES = [
    START_DATE,
    START_DATE + timedelta(days=1),
    START_DATE + timedelta(days=2),
    START_DATE + timedelta(days=3),
    START_DATE + timedelta(days=4),
    START_DATE + timedelta(days=5),
]


def test_create_base_schedule():
    assert schedules.Schedule()


def test_base_schedule_next_no_implemented():
    s = schedules.Schedule()
    with pytest.raises(NotImplementedError):
        s.next(1)


def test_create_no_schedule():
    assert schedules.NoSchedule()


def test_no_schedule_returns_no_dates():
    s = schedules.NoSchedule()
    assert s.next(1) == []


def test_create_interval_schedule():
    assert schedules.IntervalSchedule(
        start_date=pendulum.now("utc"), interval=timedelta(days=1)
    )


def test_interval_schedule_interval_must_be_positive():
    with pytest.raises(ValueError):
        schedules.IntervalSchedule(pendulum.now("utc"), interval=timedelta(hours=-1))


def test_interval_schedule_next_n():

    start_date = pendulum.datetime(2018, 1, 1)
    today = pendulum.today("utc")
    s = schedules.IntervalSchedule(start_date, timedelta(days=1))
    assert s.next(3) == [today.add(days=1), today.add(days=2), today.add(days=3)]


def test_interval_schedule_next_n_with_on_or_after_argument():
    start_date = pendulum.datetime(2018, 1, 1)
    today = pendulum.today("utc")
    s = schedules.IntervalSchedule(start_date, timedelta(days=1))
    assert s.next(3, on_or_after=start_date) == [
        start_date,
        start_date.add(days=1),
        start_date.add(days=2),
    ]


def test_interval_schedule_daylight_savings_time():
    dt = pendulum.datetime(2018, 11, 4, tz="America/New_York")
    s = schedules.IntervalSchedule(dt, timedelta(hours=1))
    next_4 = s.next(4, on_or_after=dt)
    assert [t.hour for t in next_4] == [0, 1, 1, 2]


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
    assert s.next(3) == [
        pendulum.today("utc").add(days=1),
        pendulum.today("utc").add(days=2),
        pendulum.today("utc").add(days=3),
    ]


def test_cron_schedule_next_n_with_on_or_after_argument():
    every_day = "0 0 * * *"
    s = schedules.CronSchedule(every_day)
    start_date = pendulum.datetime(2018, 1, 1)

    assert s.next(3, on_or_after=start_date) == [
        start_date,
        start_date.add(days=1),
        start_date.add(days=2),
    ]


@pytest.mark.xfail("Cron seems to have issues with DST")
def test_cron_schedule_daylight_savings_time():
    """
    Cron's behavior is to skip the 2am hour altogether, which seems wrong??

    See also https://github.com/taichino/croniter/issues/116
    """
    dt = pendulum.datetime(2018, 11, 4, tz="America/New_York")
    every_day = "0 * * * *"
    s = schedules.CronSchedule(every_day)
    next_4 = s.next(4, on_or_after=dt)
    assert [t.hour for t in next_4] == [0, 1, 1, 2]


def test_create_date_schedule():
    s = schedules.DateSchedule(DATES)
    assert s.dates == DATES


def test_date_schedule_next_n():
    s = schedules.DateSchedule(DATES)
    assert s.next(3) == DATES[:3]


def test_date_schedule_next_n_with_on_or_after_argument():
    s = schedules.DateSchedule(DATES)
    assert s.next(3, on_or_after=START_DATE + timedelta(days=4)) == DATES[3:]


def test_date_schedule_after_last_date_returns_empty_list():
    s = schedules.DateSchedule(DATES)
    assert s.next(3, on_or_after=START_DATE + timedelta(days=100)) == []


class TestSerialization:
    def test_serialize_no_schedule(self):
        schedule = schedules.NoSchedule()
        assert schedule.serialize() == {
            "type": "NoSchedule",
            "__version__": __version__,
        }

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

    def test_serialize_date_schedule(self):
        schedule = schedules.DateSchedule(dates=DATES)
        assert schedule.serialize() == {
            "type": "DateSchedule",
            "dates": [d.isoformat() for d in DATES],
            "__version__": __version__,
        }
