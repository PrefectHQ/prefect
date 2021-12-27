import itertools
from datetime import time, timedelta
from dateutil import rrule

import pendulum
import pytest

from prefect import __version__
from prefect.schedules import clocks
from prefect.serialization.schedule import ClockSchema


def islice(generator, n):
    return list(itertools.islice(generator, n))


def test_create_base_clock():
    assert clocks.Clock()


def test_base_clock_events_not_implemented():
    c = clocks.Clock()
    with pytest.raises(NotImplementedError):
        next(c.events())


class TestClockEvent:
    def test_clock_event_requires_start_time(self):
        with pytest.raises(TypeError):
            clocks.ClockEvent()

        now = pendulum.now("UTC")
        e = clocks.ClockEvent(now)

        assert e.start_time == now
        assert e.parameter_defaults == dict()
        assert e.labels is None

    def test_clock_event_accepts_parameters(self):
        now = pendulum.now("UTC")
        e = clocks.ClockEvent(now, parameter_defaults=dict(x=42, z=[1, 2, 3]))

        assert e.start_time == now
        assert e.parameter_defaults == dict(x=42, z=[1, 2, 3])
        assert e.labels is None

    def test_clock_event_accepts_labels(self):
        now = pendulum.now("UTC")
        e = clocks.ClockEvent(now, labels=["dev", "staging"])

        assert e.start_time == now
        assert e.parameter_defaults == dict()
        assert e.labels == ["dev", "staging"]

    def test_clock_event_comparisons_are_datetime_comparisons(self):
        now = pendulum.now("UTC")
        dt = now.add(hours=1)

        e = clocks.ClockEvent(now)
        e2 = clocks.ClockEvent(dt)

        ## compare to raw datetimes
        assert e == now
        assert (e == dt) == (now == dt)
        assert (e < dt) == (now < dt)
        assert (e > dt) == (now > dt)

        ## compare to other events
        assert e == clocks.ClockEvent(now)
        assert (e == e2) == (e.start_time == e2.start_time)
        assert (e < e2) == (e.start_time < e2.start_time)
        assert (e > e2) == (e.start_time > e2.start_time)

    def test_clock_event_comparisons_take_parameters_into_account(self):
        now = pendulum.now("UTC")
        dt = now.add(hours=1)

        e = clocks.ClockEvent(now, parameter_defaults=dict(a=1))
        e2 = clocks.ClockEvent(dt)
        e3 = clocks.ClockEvent(dt, parameter_defaults=dict(a=2))

        ## compare to raw datetimes
        assert e2 == dt
        assert e == now
        assert e3 == dt
        assert e2 > now
        assert e3 > now

        ## compare to each other
        assert e2 != e3
        assert e2 > e
        assert e3 > e

    def test_clock_event_comparisons_take_labels_into_account(self):
        now = pendulum.now("UTC")
        dt = now.add(hours=1)

        e = clocks.ClockEvent(now, labels=["dev"])
        e2 = clocks.ClockEvent(dt)
        e3 = clocks.ClockEvent(dt, labels=["staging"])

        ## compare to raw datetimes
        assert e2 == dt
        assert e == now
        assert e3 == dt
        assert e2 > now
        assert e3 > now

        ## compare to each other
        assert e2 != e3
        assert e2 > e
        assert e3 > e


class TestIntervalClock:
    def test_create_interval_clock(self):
        c = clocks.IntervalClock(
            start_date=pendulum.now("UTC"), interval=timedelta(days=1)
        )
        assert c.parameter_defaults == dict()
        assert c.labels is None

    def test_create_interval_clock_with_parameters(self):
        c = clocks.IntervalClock(
            start_date=pendulum.now("UTC"),
            interval=timedelta(days=1),
            parameter_defaults=dict(x=42),
        )
        assert c.parameter_defaults == dict(x=42)

    def test_create_interval_clock_with_labels(self):
        c = clocks.IntervalClock(
            start_date=pendulum.now("UTC"),
            interval=timedelta(days=1),
            labels=["foo"],
        )
        assert c.labels == ["foo"]

    def test_create_interval_clock_without_interval(self):
        with pytest.raises(TypeError):
            clocks.IntervalClock(interval=None)

    def test_start_date_can_be_none(self):
        c = clocks.IntervalClock(timedelta(hours=1))
        assert c.start_date is None
        assert c.interval == timedelta(hours=1)
        assert c.end_date is None
        assert c.parameter_defaults == dict()
        assert c.labels is None

    def test_end_date(self):
        c = clocks.IntervalClock(
            timedelta(hours=1), end_date=pendulum.datetime(2020, 1, 1)
        )
        assert c.start_date is None
        assert c.interval == timedelta(hours=1)
        assert c.end_date == pendulum.datetime(2020, 1, 1)
        assert c.parameter_defaults == dict()
        assert c.labels is None

    def test_interval_clock_interval_must_be_positive(self):
        with pytest.raises(ValueError, match="greater than 0"):
            clocks.IntervalClock(interval=timedelta(hours=-1))
        with pytest.raises(ValueError, match="greater than 0"):
            clocks.IntervalClock(interval=timedelta(seconds=-1))
        with pytest.raises(ValueError, match="greater than 0"):
            clocks.IntervalClock(interval=timedelta(0))

    @pytest.mark.parametrize("params", [dict(), dict(x=1)])
    def test_interval_clock_events(self, params):
        """Test that default after is *now*"""
        start_date = pendulum.datetime(2018, 1, 1)
        today = pendulum.today("UTC")
        c = clocks.IntervalClock(
            timedelta(days=1), start_date=start_date, parameter_defaults=params
        )
        output = islice(c.events(), 3)
        assert all(isinstance(e, clocks.ClockEvent) for e in output)
        assert all(e.parameter_defaults == params for e in output)
        assert output == [
            today.add(days=1),
            today.add(days=2),
            today.add(days=3),
        ]

    @pytest.mark.parametrize("labels", [[], ["dev"]])
    def test_interval_clock_events_with_labels(self, labels):
        """Test that default after is *now*"""
        start_date = pendulum.datetime(2018, 1, 1)
        today = pendulum.today("UTC")
        c = clocks.IntervalClock(
            timedelta(days=1), start_date=start_date, labels=labels
        )
        output = islice(c.events(), 3)
        assert all(isinstance(e, clocks.ClockEvent) for e in output)
        assert all(e.labels == labels for e in output)
        assert output == [
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

    def test_interval_clock_always_has_the_right_offset(self):
        """
        Tests the situation where a long duration has passed since the start date that crosses a DST boundary;
        for very short intervals this occasionally could result in "next" scheduled times that are in the past by one hour.
        """
        start_date = pendulum.from_timestamp(1582002945.964696).astimezone(
            pendulum.timezone("US/Pacific")
        )
        current_date = pendulum.from_timestamp(1593643144.233938).astimezone(
            pendulum.timezone("UTC")
        )
        c = clocks.IntervalClock(
            timedelta(minutes=1, seconds=15), start_date=start_date
        )
        next_4 = islice(c.events(after=current_date), 4)
        assert all(d > current_date for d in next_4)

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            0,
            1,
            3,
            4,
        ]
        # constant hourly schedule in utc time
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            0,
            1,
            3,
            4,
        ]
        # constant hourly schedule in utc time
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            0,
            1,
            1,
            2,
        ]
        # runs every hour UTC
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [4, 5, 6, 7]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            9,
            9,
            9,
            9,
        ]
        # utc time shifts
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [14, 14, 13, 13]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            9,
            9,
            9,
            9,
        ]
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [13, 13, 14, 14]


class TestCronClock:
    def test_create_cron_clock(self):
        c = clocks.CronClock("* * * * *")
        assert c.parameter_defaults == dict()
        assert c.labels is None

    def test_create_cron_clock_with_parameters(self):
        c = clocks.CronClock("* * * * *", parameter_defaults=dict(x=42))
        assert c.parameter_defaults == dict(x=42)

    def test_create_cron_clock_with_labels(self):
        c = clocks.CronClock("* * * * *", labels=["dev", "foo"])
        assert c.labels == ["dev", "foo"]

    @pytest.mark.parametrize(
        "input_day_or,expected_day_or", [(True, True), (False, False), (None, True)]
    )
    def test_create_cron_clock_with_day_or(self, input_day_or, expected_day_or):
        c = clocks.CronClock("* * * * *", day_or=input_day_or)
        assert c.day_or is expected_day_or

    def test_create_cron_clock_with_invalid_cron_string_raises_error(self):
        with pytest.raises(Exception):
            clocks.CronClock("*")
        with pytest.raises(Exception):
            clocks.CronClock("hello world")
        with pytest.raises(Exception):
            clocks.CronClock(1)
        with pytest.raises(Exception):
            clocks.CronClock("* * 32 1 1")

    @pytest.mark.parametrize("params", [dict(), dict(x=1)])
    def test_cron_clock_events(self, params):
        every_day = "0 0 * * *"
        c = clocks.CronClock(every_day, parameter_defaults=params)

        output = islice(c.events(), 3)
        assert all(isinstance(e, clocks.ClockEvent) for e in output)
        assert all(e.parameter_defaults == params for e in output)

        assert output == [
            pendulum.today("UTC").add(days=1),
            pendulum.today("UTC").add(days=2),
            pendulum.today("UTC").add(days=3),
        ]

    @pytest.mark.parametrize("labels", [[], ["foo"]])
    def test_cron_clock_events(self, labels):
        every_day = "0 0 * * *"
        c = clocks.CronClock(every_day, labels=labels)

        output = islice(c.events(), 3)
        assert all(isinstance(e, clocks.ClockEvent) for e in output)
        assert all(e.labels == labels for e in output)

        assert output == [
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

    def test_cron_clock_events_with_day_or(self):
        """At first tuesday of each month. Check if cron work as
        expected using day_or parameter.
        """
        every_day = "0 0 1-7 * 2"
        c = clocks.CronClock(every_day, day_or=False)
        output = islice(c.events(), 3)
        first_event, next_events = output[0], output[1:]
        # one event every month
        assert [event.start_time.month for event in next_events] == [
            first_event.start_time.add(months=1).month,
            first_event.start_time.add(months=2).month,
        ]

    def test_cron_clock_start_daylight_savings_time(self):
        """
        On 3/11/2018, at 2am, America/New_York switched clocks forward an hour.
        """
        dt = pendulum.datetime(2018, 3, 11, tz="America/New_York")
        every_hour = "0 * * * *"
        c = clocks.CronClock(every_hour)
        next_4 = islice(c.events(after=dt), 4)

        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [6, 7, 8, 9]

    def test_cron_clock_end_daylight_savings_time(self):
        """
        11/4/2018, at 2am, America/New_York switched clocks back an hour.
        """
        dt = pendulum.datetime(2018, 11, 4, tz="America/New_York")
        every_hour = "0 * * * *"
        c = clocks.CronClock(every_hour)
        next_4 = islice(c.events(after=dt), 4)
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            0,
            1,
            3,
            4,
        ]
        # constant hourly schedule in utc time
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            0,
            1,
            3,
            4,
        ]
        # constant hourly schedule in utc time
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [5, 6, 7, 8]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            0,
            1,
            2,
            3,
        ]
        # runs every hour UTC
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [4, 6, 7, 8]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            9,
            9,
            9,
            9,
        ]
        # utc time shifts
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [14, 14, 13, 13]

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
        assert [t.start_time.in_tz("America/New_York").hour for t in next_4] == [
            9,
            9,
            9,
            9,
        ]
        assert [t.start_time.in_tz("UTC").hour for t in next_4] == [13, 13, 14, 14]


class TestDatesClock:
    def test_create_dates_clock_one_date(self):
        now = pendulum.now("UTC")
        clock = clocks.DatesClock(dates=[now])
        assert clock.start_date == clock.end_date == now
        assert clock.parameter_defaults == dict()
        assert clock.labels is None

    def test_create_dates_clock_multiple_dates(self):
        now = pendulum.now("UTC")
        clock = clocks.DatesClock(dates=[now.add(days=1), now.add(days=2), now])
        assert clock.start_date == now
        assert clock.end_date == now.add(days=2)
        assert clock.parameter_defaults == dict()
        assert clock.labels is None

    def test_create_dates_clock_multiple_dates_with_parameters(self):
        now = pendulum.now("UTC")
        clock = clocks.DatesClock(
            dates=[now.add(days=1), now.add(days=2), now], parameter_defaults=dict(y=99)
        )
        assert clock.start_date == now
        assert clock.end_date == now.add(days=2)
        assert clock.parameter_defaults == dict(y=99)

    def test_create_dates_clock_multiple_dates_with_labels(self):
        now = pendulum.now("UTC")
        clock = clocks.DatesClock(
            dates=[now.add(days=1), now.add(days=2), now], labels=["dev", "staging"]
        )
        assert clock.start_date == now
        assert clock.end_date == now.add(days=2)
        assert clock.parameter_defaults == dict()
        assert clock.labels == ["dev", "staging"]

    def test_start_date_must_be_provided(self):
        with pytest.raises(TypeError):
            clocks.DatesClock()

    @pytest.mark.parametrize("params", [dict(), dict(x=1)])
    def test_dates_clock_events(self, params):
        """Test that default after is *now*"""
        start_date = pendulum.today("UTC").add(days=1)
        c = clocks.DatesClock([start_date], parameter_defaults=params)

        output = islice(c.events(), 3)
        assert all(isinstance(e, clocks.ClockEvent) for e in output)
        assert all(e.parameter_defaults == params for e in output)

        assert output == [start_date]
        assert islice(c.events(), 1) == [start_date]

    @pytest.mark.parametrize("labels", [[], ["foo", "bar"]])
    def test_dates_clock_events_with_labels(self, labels):
        """Test that default after is *now*"""
        start_date = pendulum.today("UTC").add(days=1)
        c = clocks.DatesClock([start_date], labels=labels)

        output = islice(c.events(), 3)
        assert all(isinstance(e, clocks.ClockEvent) for e in output)
        assert all(e.labels == labels for e in output)

        assert output == [start_date]
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


class TestRRuleClock:
    def test_rrule_clock_creation(self):
        c = clocks.RRuleClock(rrule.rrule(freq=rrule.DAILY))
        assert c.parameter_defaults == dict()
        assert c.labels is None
        assert c.start_date is None
        assert c.end_date is None

    def test_rrule_create_without_rrule(self):
        with pytest.raises(TypeError):
            clocks.RRuleClock(42)

    @pytest.mark.parametrize("params", [dict(), dict(x=1)])
    @pytest.mark.parametrize("labels", [[], ["dev"]])
    def test_rrule_clock_events(self, params, labels):
        start = pendulum.now().replace(microsecond=0)
        c = clocks.RRuleClock(
            rrule.rrule(freq=rrule.DAILY, dtstart=start),
            parameter_defaults=params,
            labels=labels,
        )

        output = islice(c.events(), 3)
        assert all(isinstance(e, clocks.ClockEvent) for e in output)
        assert all(e.parameter_defaults == params for e in output)
        assert all(e.labels == labels for e in output)
        assert output == [
            start.add(days=1),
            start.add(days=2),
            start.add(days=3),
        ]

    def test_rrule_clock_events_with_after_argument(self):
        start_date = pendulum.datetime(2018, 1, 1, microsecond=0)
        after = pendulum.datetime(2025, 1, 5)
        c = clocks.RRuleClock(rrule.rrule(freq=rrule.HOURLY, dtstart=start_date))
        assert islice(c.events(after=after), 3) == [
            after.add(hours=1),
            after.add(hours=2),
            after.add(hours=3),
        ]

    def test_rrule_clock_doesnt_compute_dates_before_start_date(self):
        dtstart = pendulum.datetime(2018, 1, 1, microsecond=0)
        start_date = pendulum.datetime(2020, 1, 1, microsecond=0)
        c = clocks.RRuleClock(
            rrule.rrule(freq=rrule.HOURLY, dtstart=dtstart), start_date=start_date
        )
        assert islice(c.events(after=pendulum.datetime(2000, 1, 1)), 3) == [
            start_date,
            start_date.add(hours=1),
            start_date.add(hours=2),
        ]

    def test_rrule_clock_doesnt_compute_dates_after_end_date(self):
        dtstart = pendulum.datetime(2018, 1, 1, microsecond=0)
        end_date = pendulum.datetime(2020, 1, 1, microsecond=0)
        c = clocks.RRuleClock(
            rrule.rrule(freq=rrule.DAILY, dtstart=dtstart), end_date=end_date
        )
        assert islice(c.events(after=end_date), 3) == []

        after = end_date.subtract(days=2)
        assert islice(c.events(after=after), 3) == [
            after.add(days=1),
            after.add(days=2),
        ]
