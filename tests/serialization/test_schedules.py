import json
from datetime import timedelta

import pendulum
import pytest
from dateutil import rrule

import prefect
from prefect import __version__
from prefect.schedules import adjustments, clocks, filters, schedules
from prefect.serialization.schedule import ScheduleSchema


def serialize_and_deserialize(schedule: schedules.Schedule) -> schedules.Schedule:
    schema = ScheduleSchema()
    return schema.load(json.loads(json.dumps(schema.dump(schedule))))


def test_serialize_schedule_with_dateclock():
    dt = pendulum.datetime(2099, 1, 1)
    s = schedules.Schedule(clocks=[clocks.DatesClock(dates=[dt, dt.add(days=1)])])
    s2 = serialize_and_deserialize(s)
    assert s2.next(2) == [dt, dt.add(days=1)]


def test_serialize_schedule_with_parameters():
    dt = pendulum.datetime(2099, 1, 1)
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(timedelta(hours=1), parameter_defaults=dict(x=42)),
            clocks.CronClock("0 8 * * *", parameter_defaults=dict(y=99)),
        ]
    )
    s2 = serialize_and_deserialize(s)

    assert s2.clocks[0].parameter_defaults == dict(x=42)
    assert s2.clocks[1].parameter_defaults == dict(y=99)

    output = s2.next(3, after=dt, return_events=True)

    assert all(e.labels is None for e in output)
    assert all(isinstance(e, clocks.ClockEvent) for e in output)


def test_serialize_schedule_with_labels():
    dt = pendulum.datetime(2099, 1, 1)
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(timedelta(hours=1), labels=["dev"]),
            clocks.CronClock("0 8 * * *", labels=["prod"]),
        ]
    )
    s2 = serialize_and_deserialize(s)

    assert s2.clocks[0].labels == ["dev"]
    assert s2.clocks[1].labels == ["prod"]

    output = s2.next(3, after=dt, return_events=True)

    assert all(isinstance(e, clocks.ClockEvent) for e in output)


def test_serialize_complex_schedule():
    dt = pendulum.datetime(2019, 1, 3)
    s = schedules.Schedule(
        # fire every hour
        clocks=[clocks.IntervalClock(timedelta(hours=1))],
        # only on weekdays
        filters=[filters.is_weekday],
        # only at 9am or 3pm
        or_filters=[
            filters.at_time(pendulum.time(9)),
            filters.between_times(pendulum.time(15), pendulum.time(15)),
        ],
        # not on january 8
        not_filters=[filters.between_dates(1, 8, 1, 8)],
        # add three hours
        adjustments=[adjustments.add(timedelta(hours=3))],
    )

    s2 = serialize_and_deserialize(s)

    assert s2.next(8, after=dt) == [
        dt.replace(hour=12),
        dt.replace(hour=18),
        dt.add(days=1).replace(hour=12),
        dt.add(days=1).replace(hour=18),
        # skip weekend
        dt.add(days=4).replace(hour=12),
        dt.add(days=4).replace(hour=18),
        # skip jan 8!
        dt.add(days=6).replace(hour=12),
        dt.add(days=6).replace(hour=18),
    ]


def test_interval_clocks_with_sub_minute_intervals_cant_be_serialized():
    schema = ScheduleSchema()
    s = schedules.Schedule(clocks=[clocks.IntervalClock(timedelta(seconds=59))])
    with pytest.raises(ValueError, match="can not be less than one minute"):
        schema.dump(s)


def test_interval_clocks_with_sub_minute_intervals_cant_be_deserialized():
    schema = ScheduleSchema()
    s = schedules.Schedule(clocks=[clocks.IntervalClock(timedelta(seconds=100))])
    data = schema.dump(s)
    data["clocks"][0]["interval"] = 59 * 1e6
    with pytest.raises(ValueError, match="can not be less than one minute"):
        schema.load(data)


def test_interval_clocks_with_exactly_one_minute_intervals_can_be_serialized():
    s = schedules.Schedule(clocks=[clocks.IntervalClock(timedelta(seconds=60))])
    t = schedules.Schedule(clocks=[clocks.IntervalClock(timedelta(minutes=1))])
    s2 = serialize_and_deserialize(s)
    t2 = serialize_and_deserialize(t)
    assert s2.next(1, after=pendulum.datetime(2019, 1, 1)) == [
        pendulum.datetime(2019, 1, 1, 0, 1)
    ]
    assert t2.next(1, after=pendulum.datetime(2019, 1, 1)) == [
        pendulum.datetime(2019, 1, 1, 0, 1)
    ]


def test_serialize_rrule_clocks():
    start = pendulum.datetime(2020, 1, 1, 0, 0)

    rr = rrule.rrule(rrule.MINUTELY, start)
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(1, after=start) == [pendulum.datetime(2020, 1, 1, 0, 1)]
    t2 = serialize_and_deserialize(t)
    assert t2.next(1, after=start) == [pendulum.datetime(2020, 1, 1, 0, 1)]

    weekdays = (rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR)
    rr = rrule.rrule(rrule.MONTHLY, start, byweekday=weekdays, bysetpos=-1)
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(1, after=start) == [pendulum.datetime(2020, 1, 31, 0, 0)]
    t2 = serialize_and_deserialize(t)
    assert t2.next(1, after=start) == [pendulum.datetime(2020, 1, 31, 0, 0)]

    # Every weekday (BYDAY) for the next 8 weekdays (COUNT).
    rr = rrule.rrule(rrule.DAILY, start, byweekday=weekdays, count=8)
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(1, after=start) == [pendulum.datetime(2020, 1, 2, 0, 0)]
    assert len(t.next(10, after=start)) == 7
    t2 = serialize_and_deserialize(t)
    assert t2.next(1, after=start) == [pendulum.datetime(2020, 1, 2, 0, 0)]
    assert len(t2.next(10, after=start)) == 7

    # Every third year (INTERVAL) on the first Tuesday (BYDAY) after a Monday (BYMONTHDAY) in October.
    month_day = (2, 3, 4, 5, 6, 7, 8)
    rr = rrule.rrule(
        rrule.YEARLY,
        start,
        interval=3,
        bymonth=10,
        byweekday=rrule.TU,
        bymonthday=month_day,
    )
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    first = pendulum.datetime(2020, 10, 6, 0, 0)
    second = pendulum.datetime(2023, 10, 3, 0, 0)
    assert t.next(2, after=start) == [first, second]
    t2 = serialize_and_deserialize(t)
    assert t2.next(2, after=start) == [first, second]

    # Every three weeks on Sunday until 9/23/2021
    until = pendulum.datetime(2021, 9, 23)
    days = [pendulum.datetime(2020, 1, 5), pendulum.datetime(2020, 1, 26)]
    after_days = [pendulum.datetime(2021, 9, 1), pendulum.datetime(2021, 9, 5)]
    rr = rrule.rrule(rrule.WEEKLY, start, byweekday=rrule.SU, interval=3, until=until)
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(2, after=start) == days
    assert t.next(3, after=after_days[0]) == [after_days[1]]
    t2 = serialize_and_deserialize(t)
    assert t2.next(2, after=start) == days
    assert t2.next(3, after=after_days[0]) == [after_days[1]]

    rr = rrule.rrule(rrule.YEARLY, start, byyearday=200)
    days = [pendulum.datetime(2020, 7, 18), pendulum.datetime(2021, 7, 19)]
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(2, after=start) == days
    t2 = serialize_and_deserialize(t)
    assert t2.next(2, after=start) == days

    # Three days after easter annually
    rr = rrule.rrule(rrule.YEARLY, start, byeaster=3)
    days = [pendulum.datetime(2020, 4, 15), pendulum.datetime(2021, 4, 7)]
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(2, after=start) == days
    t2 = serialize_and_deserialize(t)
    assert t2.next(2, after=start) == days

    rr = rrule.rrule(rrule.WEEKLY, start, byhour=9, byminute=13, bysecond=54)
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(1, after=start) == [pendulum.datetime(2020, 1, 1, 9, 13, 54)]
    t2 = serialize_and_deserialize(t)
    assert t2.next(1, after=start) == [pendulum.datetime(2020, 1, 1, 9, 13, 54)]

    rr = rrule.rrule(rrule.YEARLY, start, byweekno=(7, 16), byweekday=rrule.WE)
    days = [pendulum.datetime(2020, 2, 12), pendulum.datetime(2020, 4, 15)]
    t = schedules.Schedule(clocks=[clocks.RRuleClock(rrule_obj=rr)])
    assert t.next(2, after=start) == days
    t2 = serialize_and_deserialize(t)
    assert t2.next(2, after=start) == days


def test_serialize_multiple_clocks():

    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(timedelta(days=1)),
            clocks.IntervalClock(
                timedelta(hours=12), start_date=pendulum.datetime(2019, 1, 3)
            ),
        ]
    )
    s2 = serialize_and_deserialize(s)

    assert s2.next(6, after=dt) == [
        dt.add(days=1),
        dt.add(days=2),
        dt.add(days=2, hours=12),
        dt.add(days=3),
        dt.add(days=3, hours=12),
        dt.add(days=4),
    ]
