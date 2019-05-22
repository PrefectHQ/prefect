from datetime import time, timedelta

import pendulum
import pytest

from prefect import __version__, schedules
from prefect.serialization.schedule import ScheduleSchema

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


def serialize_fmt(dt):
    p_dt = pendulum.instance(dt)
    return dict(dt=p_dt.naive().to_iso8601_string(), tz=p_dt.tzinfo.name)


class TestIntervalSchedule:
    def test_create_interval_schedule(self):
        assert schedules.IntervalSchedule(
            start_date=pendulum.now("UTC"), interval=timedelta(days=1)
        )

    def test_start_date_must_be_datetime(self):
        with pytest.raises(TypeError):
            schedules.IntervalSchedule(start_date=None, interval=timedelta(hours=-1))

    def test_interval_schedule_interval_must_be_positive(self):
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(
                pendulum.now("UTC"), interval=timedelta(hours=-1)
            )

    def test_interval_schedule_interval_must_be_more_than_one_minute(self):
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(
                pendulum.now("UTC"), interval=timedelta(seconds=59)
            )
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(
                pendulum.now("UTC"), interval=timedelta(microseconds=59999999)
            )
        with pytest.raises(ValueError):
            schedules.IntervalSchedule(pendulum.now("UTC"), interval=timedelta(0))

    def test_interval_schedule_can_be_exactly_one_minute(self):
        assert schedules.IntervalSchedule(
            pendulum.now("UTC"), interval=timedelta(minutes=1)
        )
        assert schedules.IntervalSchedule(
            pendulum.now("UTC"), interval=timedelta(seconds=60)
        )
        assert schedules.IntervalSchedule(
            pendulum.now("UTC"), interval=timedelta(microseconds=60000000)
        )

    def test_interval_schedule_next_n(self):
        """Test that default after is *now*"""
        start_date = pendulum.datetime(2018, 1, 1)
        today = pendulum.today("UTC")
        s = schedules.IntervalSchedule(start_date, timedelta(days=1))
        assert s.next(3) == [today.add(days=1), today.add(days=2), today.add(days=3)]

    def test_interval_schedule_next_n_with_after_argument(self):
        start_date = pendulum.datetime(2018, 1, 1)
        today = pendulum.today("UTC")
        s = schedules.IntervalSchedule(start_date, timedelta(days=1))
        assert s.next(3, after=today) == [
            today.add(days=1),
            today.add(days=2),
            today.add(days=3),
        ]

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


class TestIntervalScheduleDaylightSavingsTime:
    """
    Tests that DST boundaries are respected and also serialized appropriately

    If serialize = True, the schedule is serialized and deserialized to ensure that TZ info
    survives.
    """

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_schedule_hourly_daylight_savings_time_forward_with_UTC(
        self, serialize
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        s = schedules.IntervalSchedule(dt.in_tz("UTC"), timedelta(hours=1))
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_schedule_hourly_daylight_savings_time_forward(self, serialize):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        s = schedules.IntervalSchedule(dt, timedelta(hours=1))
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_schedule_hourly_daylight_savings_time_backward(self, serialize):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 3, 23, tz="America/New_York")
        s = schedules.IntervalSchedule(dt, timedelta(hours=1))
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # repeat the 1am run in local time
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 1, 2]
        # runs every hour UTC
        assert [t.in_tz("UTC").hour for t in next_4] == [4, 5, 6, 7]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_schedule_daily_start_daylight_savings_time_forward(
        self, serialize
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 3, 8, 9, tz="America/New_York")
        s = schedules.IntervalSchedule(dt, timedelta(days=1))
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        # utc time shifts
        assert [t.in_tz("UTC").hour for t in next_4] == [14, 14, 13, 13]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_schedule_daily_start_daylight_savings_time_backward(
        self, serialize
    ):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 11, 1, 9, tz="America/New_York")
        s = schedules.IntervalSchedule(dt, timedelta(days=1))
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        assert [t.in_tz("UTC").hour for t in next_4] == [13, 13, 14, 14]


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
            schedules.CronSchedule("* * 32 1 1")

    def test_cron_schedule_next_n(self):
        every_day = "0 0 * * *"
        s = schedules.CronSchedule(every_day)
        assert s.next(3) == [
            pendulum.today("UTC").add(days=1),
            pendulum.today("UTC").add(days=2),
            pendulum.today("UTC").add(days=3),
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
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 11, tz="America/New_York")
        every_hour = "0 * * * *"
        s = schedules.CronSchedule(every_hour)
        next_4 = s.next(4, after=dt)

        assert [t.in_tz("UTC").hour for t in next_4] == [6, 7, 8, 9]

    def test_cron_schedule_end_daylight_savings_time(self):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 4, tz="America/New_York")
        every_hour = "0 * * * *"
        s = schedules.CronSchedule(every_hour)
        next_4 = s.next(4, after=dt)
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

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


class TestCronScheduleDaylightSavingsTime:
    """
    Tests that DST boundaries are respected and also serialized appropriately

    If serialize = True, the schedule is serialized and deserialized to ensure that TZ info
    survives.
    """

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_schedule_hourly_daylight_savings_time_forward_ignored_with_UTC(
        self, serialize
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        s = schedules.CronSchedule("0 * * * *", dt.in_tz("UTC"))
        if serialize:
            s = ScheduleSchema().load(s.serialize())

        next_4 = s.next(4, after=dt)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_schedule_hourly_daylight_savings_time_forward(self, serialize):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        s = schedules.CronSchedule("0 * * * *", dt)
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_schedule_hourly_daylight_savings_time_backward(self, serialize):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 3, 23, tz="America/New_York")
        s = schedules.CronSchedule("0 * * * *", dt)
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # repeat the 1am run in local time
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 2, 3]
        # runs every hour UTC
        assert [t.in_tz("UTC").hour for t in next_4] == [4, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_schedule_daily_start_daylight_savings_time_forward(self, serialize):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 3, 8, 9, tz="America/New_York")
        s = schedules.CronSchedule("0 9 * * *", dt)
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        # utc time shifts
        assert [t.in_tz("UTC").hour for t in next_4] == [14, 14, 13, 13]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_schedule_daily_start_daylight_savings_time_backward(self, serialize):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 11, 1, 9, tz="America/New_York")
        s = schedules.CronSchedule("0 9 * * *", dt)
        if serialize:
            s = ScheduleSchema().load(s.serialize())
        next_4 = s.next(4, after=dt)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        assert [t.in_tz("UTC").hour for t in next_4] == [13, 13, 14, 14]


class TestOneTimeSchedule:
    def test_create_onetime_schedule(self):
        schedule = schedules.OneTimeSchedule(start_date=pendulum.now("UTC"))
        assert schedule.start_date == schedule.end_date

    def test_start_date_must_be_provided(self):
        with pytest.raises(TypeError):
            schedules.OneTimeSchedule()

    def test_start_date_must_be_datetime(self):
        with pytest.raises(TypeError):
            schedules.OneTimeSchedule(start_date=None)

    def test_onetime_schedule_next_n(self):
        """Test that default after is *now*"""
        start_date = pendulum.today("UTC").add(days=1)
        s = schedules.OneTimeSchedule(start_date)
        assert s.next(3) == [start_date]
        assert s.next(1) == [start_date]

    def test_onetime_schedule_next_n_with_after_argument(self):
        start_date = pendulum.today("UTC").add(days=1)
        s = schedules.OneTimeSchedule(start_date)
        assert s.next(1, after=start_date - timedelta(seconds=1)) == [start_date]
        assert s.next(1, after=start_date.add(days=-1)) == [start_date]
        assert s.next(1, after=start_date.add(days=1)) == []

    def test_onetime_schedule_n_equals_0(self):
        start_date = pendulum.today("UTC").add(days=1)
        s = schedules.OneTimeSchedule(start_date=start_date)
        assert s.next(0) == []

    def test_onetime_schedule_n_negative(self):
        start_date = pendulum.today("UTC").add(days=1)
        s = schedules.OneTimeSchedule(start_date=start_date)
        assert s.next(-3) == []


class TestSerialization:
    def test_serialize_onetime_schedule(self):
        start_date = pendulum.datetime(1986, 9, 20)
        schedule = schedules.OneTimeSchedule(start_date=start_date)
        assert schedule.serialize() == {
            "start_date": serialize_fmt(start_date),
            "type": "OneTimeSchedule",
            "__version__": __version__,
        }

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
            "start_date": serialize_fmt(sd),
            "end_date": serialize_fmt(ed),
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
            "start_date": serialize_fmt(sd),
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
            "start_date": serialize_fmt(sd),
            "end_date": serialize_fmt(ed),
            "interval": 3600000000,
            "__version__": __version__,
        }


class TestUnionSchedule:
    @pytest.fixture
    def list_of_schedules(self):
        sd = pendulum.datetime(2000, 1, 1)
        ed = pendulum.datetime(2010, 1, 1)

        list_sched = []
        list_sched.append(
            schedules.IntervalSchedule(
                interval=timedelta(hours=1), start_date=sd, end_date=ed
            )
        )

        sd = pendulum.datetime(2004, 1, 1)
        ed = pendulum.datetime(2017, 1, 1)
        list_sched.append(
            schedules.CronSchedule("0 0 * * *", start_date=sd, end_date=ed)
        )
        list_sched.append(schedules.CronSchedule("0 9 * * 1-5"))
        return list_sched

    def test_initialization(self):
        s = schedules.UnionSchedule()
        assert s.start_date is None
        assert s.end_date is None

    def test_initialization_with_schedules(self, list_of_schedules):
        s = schedules.UnionSchedule(list_of_schedules)
        assert s.start_date == pendulum.datetime(2000, 1, 1)
        assert s.end_date == pendulum.datetime(2017, 1, 1)

    def test_next_n(self):
        start_date = pendulum.datetime(2018, 1, 1)
        now = pendulum.now("UTC")
        s = schedules.IntervalSchedule(start_date, timedelta(days=1))
        t = schedules.OneTimeSchedule(start_date=s.next(1)[0].add(minutes=-1))
        main = schedules.UnionSchedule([s, t])
        assert main.next(2) == [t.next(1)[0], s.next(1)[0]]

    def test_next_n_with_no_next(self):
        start_date = pendulum.datetime(2018, 1, 1)
        now = pendulum.now("UTC")
        s = schedules.IntervalSchedule(start_date, timedelta(days=1))
        t = schedules.OneTimeSchedule(start_date=now.add(hours=-1))
        main = schedules.UnionSchedule([s, t])
        assert main.next(2) == s.next(2)

    def test_next_n_with_repeated_schedule_values(self):
        start_date = pendulum.datetime(2018, 1, 1)
        now = pendulum.now("UTC")
        s = schedules.IntervalSchedule(start_date, timedelta(days=1))
        main = schedules.UnionSchedule([s, s, s, s])
        assert main.next(3) == s.next(3)

    def test_next_n_with_different_timezones(self):
        east = schedules.CronSchedule(
            "0 9 * * 1-5", start_date=pendulum.parse("2019-03-14", tz="US/Eastern")
        )
        west = schedules.CronSchedule(
            "30 6 * * 1-5", start_date=pendulum.parse("2019-03-14", tz="US/Pacific")
        )
        main = schedules.UnionSchedule([east, west])

        expected = [
            east.next(1)[0],
            west.next(1)[0],
            east.next(2)[1],
            west.next(2)[1],
            east.next(3)[2],
        ]

        # there is an edge case if this test runs between 9-9:30AM EST
        assert main.next(4) in [expected[:4], expected[1:]]
