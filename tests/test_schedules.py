from datetime import time, timedelta

import pendulum
import pytest

from prefect import __version__, schedules

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


class TestIntervalSchedule:
    def test_create_interval_schedule(self):
        assert schedules.IntervalSchedule(
            start_date=pendulum.now("utc"), interval=timedelta(days=1)
        )

    def test_start_date_must_be_datetime(self):
        with pytest.raises(TypeError):
            schedules.IntervalSchedule(start_date=None, interval=timedelta(hours=-1))

    def test_interval_schedule_interval_must_be_positive(self):
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(
                pendulum.now("utc"), interval=timedelta(hours=-1)
            )

    def test_interval_schedule_interval_must_be_more_than_one_minute(self):
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(
                pendulum.now("utc"), interval=timedelta(seconds=59)
            )
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(
                pendulum.now("utc"), interval=timedelta(microseconds=59999999)
            )
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(pendulum.now("utc"), interval=timedelta(0))

    def test_interval_schedule_can_be_exactly_one_minute(self):
        assert schedules.IntervalSchedule(
            pendulum.now("utc"), interval=timedelta(minutes=1)
        )
        assert schedules.IntervalSchedule(
            pendulum.now("utc"), interval=timedelta(seconds=60)
        )
        assert schedules.IntervalSchedule(
            pendulum.now("utc"), interval=timedelta(microseconds=60000000)
        )

    def test_interval_schedule_next_n(self):
        """Test that default after is *now*"""
        start_date = pendulum.datetime(2018, 1, 1)
        today = pendulum.today("utc")
        s = schedules.IntervalSchedule(start_date, timedelta(days=1))
        assert s.next(3) == [today.add(days=1), today.add(days=2), today.add(days=3)]

    def test_interval_schedule_next_n_with_after_argument(self):
        start_date = pendulum.datetime(2018, 1, 1)
        today = pendulum.today("utc")
        s = schedules.IntervalSchedule(start_date, timedelta(days=1))
        assert s.next(3, after=today) == [
            today.add(days=1),
            today.add(days=2),
            today.add(days=3),
        ]

    def test_interval_schedule_start_daylight_savings_time(self):
        """
        On 3/11/2018, at 2am, EST switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 11, tz="America/New_York")
        s = schedules.IntervalSchedule(dt, timedelta(hours=1))
        next_4 = s.next(4, after=dt)
        assert [t.in_tz("utc").hour for t in next_4] == [6, 7, 8, 9]

    def test_interval_schedule_daylight_savings_time(self):
        """
        11/4/2018, at 2am, EST switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 4, tz="America/New_York")
        s = schedules.IntervalSchedule(dt, timedelta(hours=1))
        next_4 = s.next(4, after=dt)
        assert [t.in_tz("utc").hour for t in next_4] == [5, 6, 7, 8]

    def test_interval_schedule_end_date(self):
        start_date = pendulum.datetime(2018, 1, 1)
        end_date = pendulum.datetime(2018, 1, 2)
        s = schedules.IntervalSchedule(
            start_date=start_date, interval=timedelta(days=1), end_date=end_date
        )
        assert s.next(3, after=start_date) == [start_date.add(days=1)]
        assert s.next(3, after=pendulum.datetime(2018, 2, 1)) == []

    def test_interval_schedule_respects_after_in_middle_of_interval(self):
        """
        If the "after" date is in the middle of an interval, then the IntervalSchedule
        should advance to the next interval.
        """
        start_date = pendulum.datetime(2018, 1, 1)
        s = schedules.IntervalSchedule(
            start_date=start_date, interval=timedelta(hours=1)
        )
        assert s.next(2, after=start_date + timedelta(microseconds=1)) == [
            start_date.add(hours=1),
            start_date.add(hours=2),
        ]

    def test_interval_schedule_doesnt_compute_dates_before_start_date(self):
        start_date = pendulum.datetime(2018, 1, 1)
        s = schedules.IntervalSchedule(
            start_date=start_date, interval=timedelta(hours=1)
        )
        assert s.next(3, after=pendulum.datetime(2000, 1, 1)) == [
            start_date,
            start_date.add(hours=1),
            start_date.add(hours=2),
        ]

    def test_interval_schedule_respects_microseconds(self):
        start_date = pendulum.datetime(2018, 1, 1, 0, 0, 0, 1)
        s = schedules.IntervalSchedule(
            start_date=start_date, interval=timedelta(hours=1)
        )
        assert s.next(3, after=pendulum.datetime(2010, 1, 1)) == [
            start_date,
            start_date.add(hours=1),
            start_date.add(hours=2),
        ]

    def test_interval_schedule_n_equals_0(self):
        start_date = pendulum.datetime(2018, 1, 1)
        s = schedules.IntervalSchedule(
            start_date=start_date, interval=timedelta(hours=1)
        )
        assert s.next(0) == []

    def test_interval_schedule_n_is_negative(self):
        start_date = pendulum.datetime(2018, 1, 1)
        s = schedules.IntervalSchedule(
            start_date=start_date, interval=timedelta(hours=1)
        )
        assert s.next(-3) == []


class TestCronSchedule:
    def test_create_cron_schedule(self):
        assert schedules.CronSchedule("* * * * *")

    def test_create_cron_schedule_with_invalid_cron_string_raises_error(self):
        with pytest.raises(Exception):
            schedules.CronSchedule("*")
        with pytest.raises(Exception):
            schedules.CronSchedule("hello world")
        with pytest.raises(Exception):
            schedules.CronSchedule(1)
        with pytest.raises(Exception):
            schedules.CronSchedule("* * 0 0 0")

    def test_cron_schedule_next_n(self):
        every_day = "0 0 * * *"
        s = schedules.CronSchedule(every_day)
        assert s.next(3) == [
            pendulum.today("utc").add(days=1),
            pendulum.today("utc").add(days=2),
            pendulum.today("utc").add(days=3),
        ]

    def test_cron_schedule_next_n_with_after_argument(self):
        every_day = "0 0 * * *"
        s = schedules.CronSchedule(every_day)
        start_date = pendulum.datetime(2018, 1, 1)

        assert s.next(3, after=start_date) == [
            start_date.add(days=1),
            start_date.add(days=2),
            start_date.add(days=3),
        ]

    def test_cron_schedule_start_daylight_savings_time(self):
        """
        On 3/11/2018, at 2am, EST switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 11, tz="America/New_York")
        every_hour = "0 * * * *"
        s = schedules.CronSchedule(every_hour)
        next_4 = s.next(4, after=dt)

        assert [t.in_tz("utc").hour for t in next_4] == [6, 7, 8, 9]

    def test_cron_schedule_end_daylight_savings_time(self):
        """
        11/4/2018, at 2am, EST switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 4, tz="America/New_York")
        every_hour = "0 * * * *"
        s = schedules.CronSchedule(every_hour)
        next_4 = s.next(4, after=dt)
        assert [t.in_tz("utc").hour for t in next_4] == [5, 6, 7, 8]

    def test_cron_schedule_start_date(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1)
        s = schedules.CronSchedule(every_day, start_date=start_date)
        assert s.next(3) == [start_date, start_date.add(days=1), start_date.add(days=2)]

    def test_cron_schedule_end_date(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1)
        end_date = pendulum.datetime(2050, 1, 2)
        s = schedules.CronSchedule(every_day, start_date=start_date, end_date=end_date)
        assert s.next(3) == [start_date, start_date.add(days=1)]

    def test_cron_schedule_when_start_date_doesnt_align_with_schedule(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1, 6, 0, 0)
        s = schedules.CronSchedule(every_day, start_date=start_date)
        assert s.next(1) == [pendulum.datetime(2050, 1, 2, 0, 0, 0)]

    def test_cron_schedule_when_start_date_and_after_doesnt_align_with_schedule(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1, 6, 0, 0)
        s = schedules.CronSchedule(every_day, start_date=start_date)
        assert s.next(1, after=pendulum.datetime(2050, 1, 1, 7, 0, 0)) == [
            pendulum.datetime(2050, 1, 2, 0, 0, 0)
        ]

    def test_cron_schedule_respects_microseconds(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1, 0, 0, 0, 1)
        s = schedules.CronSchedule(every_day, start_date=start_date)
        assert s.next(1) == [pendulum.datetime(2050, 1, 2)]

    def test_cron_schedule_n_equals_0(self):
        start_date = pendulum.datetime(2018, 1, 1)
        s = schedules.CronSchedule(start_date=start_date, cron="0 0 * * *")
        assert s.next(0) == []

    def test_cron_schedule_n_is_negative(self):
        start_date = pendulum.datetime(2018, 1, 1)
        s = schedules.CronSchedule(start_date=start_date, cron="0 0 * * *")
        assert s.next(-3) == []


class TestSerialization:
    def test_serialize_cron_schedule(self):
        schedule = schedules.CronSchedule("0 0 * * *")
        assert schedule.serialize() == {
            "end_date": None,
            "start_date": None,
            "type": "CronSchedule",
            "cron": "0 0 * * *",
            "__version__": __version__,
        }

    def test_serialize_cron_schedule_with_start_and_end_dates(self):
        sd = pendulum.datetime(2000, 1, 1)
        ed = pendulum.datetime(2010, 1, 1)
        schedule = schedules.CronSchedule("0 0 * * *", start_date=sd, end_date=ed)
        assert schedule.serialize() == {
            "end_date": str(ed),
            "start_date": str(sd),
            "type": "CronSchedule",
            "cron": "0 0 * * *",
            "__version__": __version__,
        }

    def test_serialize_interval_schedule(self):
        sd = pendulum.datetime(2000, 1, 1)
        schedule = schedules.IntervalSchedule(
            interval=timedelta(hours=1), start_date=sd
        )
        assert schedule.serialize() == {
            "type": "IntervalSchedule",
            "start_date": str(sd),
            "end_date": None,
            "interval": 3600000000,
            "__version__": __version__,
        }

    def test_serialize_interval_schedule_with_end_date(self):
        sd = pendulum.datetime(2000, 1, 1)
        ed = pendulum.datetime(2010, 1, 1)

        schedule = schedules.IntervalSchedule(
            interval=timedelta(hours=1), start_date=sd, end_date=ed
        )
        assert schedule.serialize() == {
            "type": "IntervalSchedule",
            "start_date": str(sd),
            "end_date": str(ed),
            "interval": 3600000000,
            "__version__": __version__,
        }
