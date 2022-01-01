import itertools
from datetime import time, timedelta

import pendulum
import pytest

from prefect import __version__
from prefect.schedules import adjustments, clocks, filters, schedules


def test_create_schedule_requires_clock():
    with pytest.raises(TypeError):
        schedules.Schedule()


def test_create_schedule_requires_list_of_clocks():
    with pytest.raises(TypeError):
        schedules.Schedule(clocks=clocks.IntervalClock(timedelta(days=1)))


def test_schedule_with_empty_clocks():
    s = schedules.Schedule(clocks=[])
    assert s.next(3) == []


def test_create_schedule():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(clocks=[clocks.IntervalClock(timedelta(days=1))])
    output = s.next(3, after=dt)

    assert all(not isinstance(e, clocks.ClockEvent) for e in output)
    assert output == [dt.add(days=1), dt.add(days=2), dt.add(days=3)]


def test_create_schedule_emits_events_if_asked():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(clocks=[clocks.IntervalClock(timedelta(days=1))])
    output = s.next(3, after=dt, return_events=True)

    assert all(isinstance(e, clocks.ClockEvent) for e in output)
    assert all(e.parameter_defaults == dict() for e in output)

    assert output == [dt.add(days=1), dt.add(days=2), dt.add(days=3)]


def test_create_schedule_multiple_overlapping_clocks():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(timedelta(days=1)),
            clocks.IntervalClock(
                timedelta(hours=12), start_date=pendulum.datetime(2019, 1, 3)
            ),
        ]
    )
    output = s.next(6, after=dt)
    assert all(not isinstance(e, clocks.ClockEvent) for e in output)

    assert output == [
        dt.add(days=1),
        dt.add(days=2),
        dt.add(days=2, hours=12),
        dt.add(days=3),
        dt.add(days=3, hours=12),
        dt.add(days=4),
    ]


def test_create_schedule_multiple_overlapping_clocks_distinguishes_parameters():
    dt = pendulum.datetime(2019, 1, 1)
    special_day = pendulum.datetime(2020, 3, 1)
    s = schedules.Schedule(
        clocks=[
            clocks.DatesClock([special_day]),
            clocks.DatesClock([special_day]),
        ]
    )
    output = s.next(2, after=dt, return_events=True)
    assert len(output) == 1
    assert output[0].start_time == special_day

    s = schedules.Schedule(
        clocks=[
            clocks.DatesClock([special_day], parameter_defaults=dict(a=1)),
            clocks.DatesClock([special_day], parameter_defaults=dict(a=2)),
        ]
    )
    output = s.next(2, after=dt, return_events=True)
    assert len(output) == 2
    assert [e.start_time for e in output] == [special_day] * 2
    assert set(e.parameter_defaults["a"] for e in output) == {1, 2}


def test_create_schedule_multiple_overlapping_clocks_emit_events_if_asked():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(timedelta(days=1)),
            clocks.IntervalClock(
                timedelta(hours=12), start_date=pendulum.datetime(2019, 1, 3)
            ),
        ]
    )
    output = s.next(6, after=dt, return_events=True)
    assert all(isinstance(e, clocks.ClockEvent) for e in output)
    assert all(e.parameter_defaults == dict() for e in output)
    assert output == [
        dt.add(days=1),
        dt.add(days=2),
        dt.add(days=2, hours=12),
        dt.add(days=3),
        dt.add(days=3, hours=12),
        dt.add(days=4),
    ]


def test_create_schedule_multiple_overlapping_clocks_emit_events_with_correct_parameters():
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(timedelta(days=1), parameter_defaults=dict(x=0)),
            clocks.IntervalClock(timedelta(hours=12), parameter_defaults=dict(x=1)),
        ]
    )
    dt = pendulum.datetime(2019, 1, 1)
    output = s.next(6, after=dt, return_events=True)

    assert all(isinstance(e, clocks.ClockEvent) for e in output)
    assert [e.parameter_defaults["x"] for e in output] == [1, 0, 1, 1, 0, 1]
    assert [e.start_time for e in output] == [
        dt.add(hours=12),
        dt.add(days=1),
        dt.add(days=1),
        dt.add(days=1, hours=12),
        dt.add(days=2),
        dt.add(days=2),
    ]


def test_create_schedule_filters():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[clocks.IntervalClock(timedelta(hours=1))],
        filters=[filters.between_times(pendulum.time(9), pendulum.time(10))],
    )
    assert s.next(6, after=dt) == [
        dt.add(days=0).replace(hour=9),
        dt.add(days=0).replace(hour=10),
        dt.add(days=1).replace(hour=9),
        dt.add(days=1).replace(hour=10),
        dt.add(days=2).replace(hour=9),
        dt.add(days=2).replace(hour=10),
    ]


def test_create_schedule_filters_2():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[clocks.IntervalClock(timedelta(minutes=15))],
        filters=[filters.at_time(pendulum.time(2, 45))],
    )
    assert s.next(6, after=dt) == [
        dt.add(days=0, hours=2, minutes=45),
        dt.add(days=1, hours=2, minutes=45),
        dt.add(days=2, hours=2, minutes=45),
        dt.add(days=3, hours=2, minutes=45),
        dt.add(days=4, hours=2, minutes=45),
        dt.add(days=5, hours=2, minutes=45),
    ]


def test_create_schedule_multiple_exclusive_filters():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[clocks.IntervalClock(timedelta(hours=1))],
        filters=[
            filters.between_times(pendulum.time(9), pendulum.time(10)),
            filters.between_times(pendulum.time(15), pendulum.time(16)),
        ],
    )
    assert s.next(6, after=dt) == []


def test_create_schedule_or_filters():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[clocks.IntervalClock(timedelta(hours=1))],
        or_filters=[
            filters.between_times(pendulum.time(9), pendulum.time(9)),
            filters.between_times(pendulum.time(15), pendulum.time(15)),
        ],
    )

    assert s.next(6, after=dt) == [
        dt.add(days=0).replace(hour=9),
        dt.add(days=0).replace(hour=15),
        dt.add(days=1).replace(hour=9),
        dt.add(days=1).replace(hour=15),
        dt.add(days=2).replace(hour=9),
        dt.add(days=2).replace(hour=15),
    ]


def test_create_schedule_not_filters():
    dt = pendulum.datetime(2019, 1, 1)
    s = schedules.Schedule(
        clocks=[clocks.IntervalClock(timedelta(hours=1))],
        not_filters=[
            filters.between_times(pendulum.time(0), pendulum.time(8)),
            filters.between_times(pendulum.time(10), pendulum.time(14)),
            filters.between_times(pendulum.time(16), pendulum.time(23)),
        ],
    )

    assert s.next(6, after=dt) == [
        dt.add(days=0).replace(hour=9),
        dt.add(days=0).replace(hour=15),
        dt.add(days=1).replace(hour=9),
        dt.add(days=1).replace(hour=15),
        dt.add(days=2).replace(hour=9),
        dt.add(days=2).replace(hour=15),
    ]


def test_create_schedule_multiple_filters():
    # jan 3 was a thursday
    dt = pendulum.datetime(2019, 1, 3)
    s = schedules.Schedule(
        # fire every hour
        clocks=[clocks.IntervalClock(timedelta(hours=1))],
        # only on weekdays
        filters=[filters.is_weekday],
        # only at 9am or 3pm
        or_filters=[
            filters.between_times(pendulum.time(9), pendulum.time(9)),
            filters.between_times(pendulum.time(15), pendulum.time(15)),
        ],
        # not on january 8
        not_filters=[filters.between_dates(1, 8, 1, 8)],
    )

    assert s.next(8, after=dt) == [
        dt.replace(hour=9),
        dt.replace(hour=15),
        dt.add(days=1).replace(hour=9),
        dt.add(days=1).replace(hour=15),
        # skip weekend
        dt.add(days=4).replace(hour=9),
        dt.add(days=4).replace(hour=15),
        # skip jan 8!
        dt.add(days=6).replace(hour=9),
        dt.add(days=6).replace(hour=15),
    ]


def test_create_schedule_adjustments():
    # jan 3 was a thursday
    dt = pendulum.datetime(2019, 1, 3)
    s = schedules.Schedule(
        # fire every hour
        clocks=[clocks.IntervalClock(timedelta(hours=1))],
        # only on weekdays
        filters=[filters.is_weekday],
        # only at 9am or 3pm
        or_filters=[
            filters.between_times(pendulum.time(9), pendulum.time(9)),
            filters.between_times(pendulum.time(15), pendulum.time(15)),
        ],
        # not on january 8
        not_filters=[filters.between_dates(1, 8, 1, 8)],
        # add three hours
        adjustments=[adjustments.add(timedelta(hours=3))],
    )

    assert s.next(8, after=dt) == [
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


def test_start_date_and_end_date():
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(
                timedelta(hours=1),
                start_date=pendulum.datetime(2018, 1, 1),
                end_date=pendulum.datetime(2019, 1, 1),
            ),
            clocks.IntervalClock(
                timedelta(hours=1),
                start_date=pendulum.datetime(2019, 1, 1),
                end_date=pendulum.datetime(2020, 1, 1),
            ),
        ]
    )
    assert s.start_date == pendulum.datetime(2018, 1, 1)
    assert s.end_date == pendulum.datetime(2020, 1, 1)


def test_start_date_and_end_date_none():
    s = schedules.Schedule(
        clocks=[
            clocks.IntervalClock(timedelta(hours=1)),
            clocks.IntervalClock(timedelta(hours=1)),
        ]
    )
    assert s.start_date is None
    assert s.end_date is None


def test_start_date_and_end_date_missing():
    s = schedules.Schedule(clocks=[])
    assert s.start_date is None
    assert s.end_date is None


def test_with_clocks_with_different_timezones():
    east = clocks.CronClock(
        "0 9 * * 1-5", start_date=pendulum.parse("2019-03-14", tz="US/Eastern")
    )
    west = clocks.CronClock(
        "30 6 * * 1-5", start_date=pendulum.parse("2019-03-14", tz="US/Pacific")
    )
    s = schedules.Schedule(clocks=[east, west])

    after = pendulum.datetime(2019, 5, 1)
    next_east = list(itertools.islice(east.events(after=after), 3))
    next_west = list(itertools.islice(west.events(after=after), 3))
    expected = [
        next_east[0],
        next_west[0],
        next_east[1],
        next_west[1],
        next_east[2],
        next_west[2],
    ]

    assert s.next(6, after) == expected


def test_interval_schedule_requires_interval_even_though_none_default():
    """
    IntervalSchedule requires an interval, but in order to maintain the pre-0.6.1 signature,
    it has an unusual call signature.
    """
    with pytest.raises(TypeError):
        schedules.IntervalSchedule()
