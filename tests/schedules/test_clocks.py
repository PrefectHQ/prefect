from datetime import time, timedelta

import pendulum
import pytest
import itertools
from prefect import __version__
from prefect.schedules import clocks
from prefect.serialization.schedule import ClockSchema


def islice(generator, n):
    return list(itertools.islice(generator, n))


def test_create_base_clock():
    assert clocks.Clock()


def test_base_clock_eventso_implemented():
    c = clocks.Clock()
    with pytest.raises(NotImplementedError):
        next(c.events())


class TestIntervalClock:
    def test_create_interval_clock(self):
        assert clocks.IntervalClock(
            start_date=pendulum.now("UTC"), interval=timedelta(days=1)
        )

    def test_start_date_can_be_none(self):
        c = clocks.IntervalClock(timedelta(hours=1))
        assert c.start_date is None
        assert c.interval == timedelta(hours=1)
        assert c.end_date is None

    def test_end_date(self):
        c = clocks.IntervalClock(
            timedelta(hours=1), end_date=pendulum.datetime(2020, 1, 1)
        )
        assert c.start_date is None
        assert c.interval == timedelta(hours=1)
        assert c.end_date == pendulum.datetime(2020, 1, 1)

    def test_interval_clock_interval_must_be_positive(self):
        with pytest.raises(ValueError):
            clocks.IntervalClock(interval=timedelta(hours=-1))

    def test_interval_clock_interval_must_be_more_than_one_minute(self):
        with pytest.raises(ValueError):
            clocks.IntervalClock(interval=timedelta(seconds=59))
        with pytest.raises(ValueError):
            clocks.IntervalClock(interval=timedelta(microseconds=59999999))
        with pytest.raises(ValueError):
            clocks.IntervalClock(interval=timedelta(0))

    def test_interval_clock_can_be_exactly_one_minute(self):
        assert clocks.IntervalClock(interval=timedelta(minutes=1))
        assert clocks.IntervalClock(interval=timedelta(seconds=60))
        assert clocks.IntervalClock(interval=timedelta(microseconds=60000000))

    def test_interval_clock_events(self):
        """Test that default after is *now*"""
        start_date = pendulum.datetime(2018, 1, 1)
        today = pendulum.today("UTC")
        c = clocks.IntervalClock(timedelta(days=1), start_date=start_date)
        assert islice(c.events(), 3) == [
            today.add(days=1),
            today.add(days=2),
            today.add(days=3),
        ]

    def test_interval_clock_events_with_after_argument(self):
        start_date = pendulum.datetime(2018, 1, 1)
        after = pendulum.datetime(2025, 1, 5)
        c = clocks.IntervalClock(timedelta(days=1), start_date=start_date)
        assert islice(c.events(after=after.add(hours=1)), 3) == [
            after.add(days=1),
            after.add(days=2),
            after.add(days=3),
        ]

    def test_interval_clock_end_date(self):
        start_date = pendulum.datetime(2018, 1, 1)
        end_date = pendulum.datetime(2018, 1, 2)
        c = clocks.IntervalClock(
            start_date=start_date, interval=timedelta(days=1), end_date=end_date
        )
        assert islice(c.events(after=start_date), 3) == [start_date.add(days=1)]
        assert islice(c.events(after=pendulum.datetime(2018, 2, 1)), 3) == []

    def test_interval_clock_respects_after_in_middle_of_interval(self):
        """
        If the "after" date is in the middle of an interval, then the IntervalClock
        should advance to the next interval.
        """
        start_date = pendulum.datetime(2018, 1, 1)
        c = clocks.IntervalClock(start_date=start_date, interval=timedelta(hours=1))
        assert islice(c.events(after=start_date + timedelta(microseconds=1)), 2) == [
            start_date.add(hours=1),
            start_date.add(hours=2),
        ]

    def test_interval_clock_doesnt_compute_dates_before_start_date(self):
        start_date = pendulum.datetime(2018, 1, 1)
        c = clocks.IntervalClock(start_date=start_date, interval=timedelta(hours=1))
        assert islice(c.events(after=pendulum.datetime(2000, 1, 1)), 3) == [
            start_date,
            start_date.add(hours=1),
            start_date.add(hours=2),
        ]

    def test_interval_clock_respects_microseconds(self):
        start_date = pendulum.datetime(2018, 1, 1, 0, 0, 0, 1)
        c = clocks.IntervalClock(start_date=start_date, interval=timedelta(hours=1))
        assert islice(c.events(after=pendulum.datetime(2010, 1, 1)), 3) == [
            start_date,
            start_date.add(hours=1),
            start_date.add(hours=2),
        ]


class TestIntervalClockDaylightSavingsTime:
    """
    Tests that DST boundaries are respected and also serialized appropriately

    If serialize = True, the schedule is serialized and deserialized to ensure that TZ info
    survives.
    """

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_clock_hourly_daylight_savings_time_forward_with_UTC(
        self, serialize
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        c = clocks.IntervalClock(timedelta(hours=1), start_date=dt.in_tz("UTC"))
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_clock_hourly_daylight_savings_time_forward(self, serialize):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        c = clocks.IntervalClock(timedelta(hours=1), start_date=dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_clock_hourly_daylight_savings_time_backward(self, serialize):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 3, 23, tz="America/New_York")
        c = clocks.IntervalClock(timedelta(hours=1), start_date=dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # repeat the 1am run in local time
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 1, 2]
        # runs every hour UTC
        assert [t.in_tz("UTC").hour for t in next_4] == [4, 5, 6, 7]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_clock_daily_start_daylight_savings_time_forward(self, serialize):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 3, 8, 9, tz="America/New_York")
        c = clocks.IntervalClock(timedelta(days=1), start_date=dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        # utc time shifts
        assert [t.in_tz("UTC").hour for t in next_4] == [14, 14, 13, 13]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_interval_clock_daily_start_daylight_savings_time_backward(self, serialize):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 11, 1, 9, tz="America/New_York")
        c = clocks.IntervalClock(timedelta(days=1), start_date=dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        assert [t.in_tz("UTC").hour for t in next_4] == [13, 13, 14, 14]


class TestCronClock:
    def test_create_cron_clock(self):
        assert clocks.CronClock("* * * * *")

    def test_create_cron_clock_with_invalid_cron_string_raises_error(self):
        with pytest.raises(Exception):
            clocks.CronClock("*")
        with pytest.raises(Exception):
            clocks.CronClock("hello world")
        with pytest.raises(Exception):
            clocks.CronClock(1)
        with pytest.raises(Exception):
            clocks.CronClock("* * 32 1 1")

    def test_cron_clock_events(self):
        every_day = "0 0 * * *"
        c = clocks.CronClock(every_day)
        assert islice(c.events(), 3) == [
            pendulum.today("UTC").add(days=1),
            pendulum.today("UTC").add(days=2),
            pendulum.today("UTC").add(days=3),
        ]

    def test_cron_clock_events_with_after_argument(self):
        every_day = "0 0 * * *"
        c = clocks.CronClock(every_day)
        start_date = pendulum.datetime(2018, 1, 1)

        assert islice(c.events(after=start_date), 3) == [
            start_date.add(days=1),
            start_date.add(days=2),
            start_date.add(days=3),
        ]

    def test_cron_clock_start_daylight_savings_time(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 11, tz="America/New_York")
        every_hour = "0 * * * *"
        c = clocks.CronClock(every_hour)
        next_4 = islice(c.events(after=dt), 4)

        assert [t.in_tz("UTC").hour for t in next_4] == [6, 7, 8, 9]

    def test_cron_clock_end_daylight_savings_time(self):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 4, tz="America/New_York")
        every_hour = "0 * * * *"
        c = clocks.CronClock(every_hour)
        next_4 = islice(c.events(after=dt), 4)
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    def test_cron_clock_start_date(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1)
        c = clocks.CronClock(every_day, start_date=start_date)
        assert islice(c.events(), 3) == [
            start_date,
            start_date.add(days=1),
            start_date.add(days=2),
        ]

    def test_cron_clock_end_date(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1)
        end_date = pendulum.datetime(2050, 1, 2)
        c = clocks.CronClock(every_day, start_date=start_date, end_date=end_date)
        assert islice(c.events(), 3) == [start_date, start_date.add(days=1)]

    def test_cron_clock_when_start_date_doesnt_align_with_schedule(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1, 6, 0, 0)
        c = clocks.CronClock(every_day, start_date=start_date)
        assert islice(c.events(), 1) == [pendulum.datetime(2050, 1, 2, 0, 0, 0)]

    def test_cron_clock_when_start_date_and_after_doesnt_align_with_schedule(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1, 6, 0, 0)
        c = clocks.CronClock(every_day, start_date=start_date)
        assert islice(c.events(after=pendulum.datetime(2050, 1, 1, 7, 0, 0)), 1) == [
            pendulum.datetime(2050, 1, 2, 0, 0, 0)
        ]

    def test_cron_clock_respects_microseconds(self):
        every_day = "0 0 * * *"
        start_date = pendulum.datetime(2050, 1, 1, 0, 0, 0, 1)
        c = clocks.CronClock(every_day, start_date=start_date)
        assert islice(c.events(), 1) == [pendulum.datetime(2050, 1, 2)]


class TestCronClockDaylightSavingsTime:
    """
    Tests that DST boundaries are respected and also serialized appropriately

    If serialize = True, the schedule is serialized and deserialized to ensure that TZ info
    survives.
    """

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_clock_hourly_daylight_savings_time_forward_ignored_with_UTC(
        self, serialize
    ):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        c = clocks.CronClock("0 * * * *", dt.in_tz("UTC"))
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))

        next_4 = islice(c.events(after=dt), 4)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_clock_hourly_daylight_savings_time_forward(self, serialize):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 10, 23, tz="America/New_York")
        c = clocks.CronClock("0 * * * *", dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # skip 2am
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 3, 4]
        # constant hourly schedule in utc time
        assert [t.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_clock_hourly_daylight_savings_time_backward(self, serialize):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 3, 23, tz="America/New_York")
        c = clocks.CronClock("0 * * * *", dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # repeat the 1am run in local time
        assert [t.in_tz("America/New_York").hour for t in next_4] == [0, 1, 2, 3]
        # runs every hour UTC
        assert [t.in_tz("UTC").hour for t in next_4] == [4, 6, 7, 8]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_clock_daily_start_daylight_savings_time_forward(self, serialize):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 3, 8, 9, tz="America/New_York")
        c = clocks.CronClock("0 9 * * *", dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        # utc time shifts
        assert [t.in_tz("UTC").hour for t in next_4] == [14, 14, 13, 13]

    @pytest.mark.parametrize("serialize", [True, False])
    def test_cron_clock_daily_start_daylight_savings_time_backward(self, serialize):
        """
        On 11/4/2018, at 2am, America/New_York switched clocks back an hour.

        Confirm that a schedule for 9am America/New_York stays 9am through the switch.
        """
        dt = pendulum.datetime(2018, 11, 1, 9, tz="America/New_York")
        c = clocks.CronClock("0 9 * * *", dt)
        if serialize:
            c = ClockSchema().load(ClockSchema().dump(c))
        next_4 = islice(c.events(after=dt), 4)
        # constant 9am start
        assert [t.in_tz("America/New_York").hour for t in next_4] == [9, 9, 9, 9]
        assert [t.in_tz("UTC").hour for t in next_4] == [13, 13, 14, 14]


class TestDatesClock:
    def test_create_dates_clock_one_date(self):
        now = pendulum.now("UTC")
        clock = clocks.DatesClock(dates=[now])
        assert clock.start_date == clock.end_date == now

    def test_create_dates_clock_multiple_dates(self):
        now = pendulum.now("UTC")
        clock = clocks.DatesClock(dates=[now.add(days=1), now.add(days=2), now])
        assert clock.start_date == now
        assert clock.end_date == now.add(days=2)

    def test_start_date_must_be_provided(self):
        with pytest.raises(TypeError):
            clocks.DatesClock()

    def test_dates_clock_events(self):
        """Test that default after is *now*"""
        start_date = pendulum.today("UTC").add(days=1)
        c = clocks.DatesClock([start_date])
        assert islice(c.events(), 3) == [start_date]
        assert islice(c.events(), 1) == [start_date]

    def test_dates_clock_events_with_after_argument(self):
        dt = pendulum.today("UTC").add(days=1)
        c = clocks.DatesClock([dt])
        assert islice(c.events(after=dt - timedelta(seconds=1)), 1) == [dt]
        assert islice(c.events(after=dt.add(days=-1)), 1) == [dt]
        assert islice(c.events(after=dt.add(days=1)), 1) == []

    def test_dates_clock_sorted_events(self):
        dt = pendulum.now("UTC").add(days=1)

        clock = clocks.DatesClock(dates=[dt.add(days=1), dt.add(days=2), dt])
        assert islice(clock.events(), 3) == [dt, dt.add(days=1), dt.add(days=2)]
