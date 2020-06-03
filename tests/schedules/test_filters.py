import pendulum
import pytest

import prefect.schedules.filters as filters


def test_on_datetime_0():
    filter_fn = filters.on_datetime(pendulum.datetime(2019, 1, 2, 3, 4, 5))
    assert filter_fn(pendulum.datetime(2019, 1, 2, 3, 4, 5))


def test_on_datetime_1():
    filter_fn = filters.on_datetime(pendulum.datetime(2019, 1, 2))
    assert filter_fn(pendulum.datetime(2019, 1, 2))


def test_on_datetime_2():
    filter_fn = filters.on_datetime(pendulum.datetime(2019, 1, 2, 3, 4))
    assert not filter_fn(pendulum.datetime(2019, 1, 2, 3, 4, 5))


def test_on_datetime_3():
    filter_fn = filters.on_datetime(pendulum.datetime(2019, 1, 2, 3, 4, 5))
    assert not filter_fn(pendulum.datetime(2019, 1, 2, 3, 4))


@pytest.mark.parametrize(
    "test_datetimes",
    [
        (pendulum.datetime(2019, 1, 1), pendulum.datetime(2019, 1, 2), True),
        (pendulum.datetime(2019, 1, 1), pendulum.datetime(2019, 1, 1), False),
        (pendulum.datetime(2019, 1, 2), pendulum.datetime(2019, 1, 2), False),
        (pendulum.datetime(2019, 1, 1, 6), pendulum.datetime(2019, 1, 1, 6), True),
        (
            pendulum.datetime(2019, 1, 1, 5, 59),
            pendulum.datetime(2019, 1, 1, 6, 1),
            True,
        ),
    ],
)
def test_between_datetimes(test_datetimes):
    dt = pendulum.datetime(2019, 1, 1, 6)
    filter_fn = filters.between_datetimes(test_datetimes[0], test_datetimes[1])
    assert filter_fn(dt) is test_datetimes[2]


def test_on_date():
    filter_fn = filters.on_date(3, 4)

    assert filter_fn(pendulum.datetime(2019, 3, 4))
    assert not filter_fn(pendulum.datetime(2019, 3, 5))
    assert filter_fn(pendulum.datetime(2019, 3, 4, 5, 6))
    assert filter_fn(pendulum.datetime(2034, 3, 4))
    assert not filter_fn(pendulum.datetime(2034, 3, 5))
    assert not filter_fn(pendulum.datetime(2034, 4, 4))


@pytest.mark.parametrize(
    "test_dates",
    [
        ((1, 1, 12, 31), True),
        ((6, 1, 6, 1), True),
        ((5, 31, 6, 2), True),
        ((6, 2, 5, 31), False),
        ((6, 2, 7, 1), False),
        ((11, 1, 7, 1), True),
    ],
)
def test_between_dates(test_dates):
    dt = pendulum.datetime(2019, 6, 1)
    filter_fn = filters.between_dates(*test_dates[0])
    assert filter_fn(dt) is test_dates[1]


@pytest.mark.parametrize(
    "test_times",
    [
        (pendulum.datetime(2019, 1, 2, 4, 30), False),
        (pendulum.datetime(2019, 1, 2, 3, 30), True),
        (pendulum.datetime(2020, 1, 2, 3, 30), True),
        (pendulum.datetime(2019, 4, 5, 3, 30), True),
        (pendulum.datetime(2019, 4, 5, 3, 30, 1), False),
    ],
)
def test_at_time(test_times):
    test_dt, result = test_times
    filter_fn = filters.at_time(pendulum.time(3, 30))
    assert filter_fn(test_dt) is result


@pytest.mark.parametrize(
    "test_times",
    [
        (pendulum.time(5), pendulum.time(7), True),
        (pendulum.time(6), pendulum.time(6), True),
        (pendulum.time(7), pendulum.time(5), False),
        (pendulum.time(7), pendulum.time(6), True),
    ],
)
def test_between_times(test_times):
    dt = pendulum.datetime(2019, 6, 1, 6)
    filter_fn = filters.between_times(test_times[0], test_times[1])
    assert filter_fn(dt) is test_times[2]


@pytest.mark.parametrize("dt", [pendulum.datetime(2019, 1, i) for i in range(1, 10)])
def test_is_weekday(dt):
    assert filters.is_weekday(dt) == (dt.weekday() < 5)


@pytest.mark.parametrize("dt", [pendulum.datetime(2019, 1, i) for i in range(1, 10)])
def test_is_weekend(dt):
    assert filters.is_weekend(dt) == (dt.weekday() > 4)


@pytest.mark.parametrize(
    "dates",
    [
        (pendulum.datetime(2019, 1, 20), False),
        (pendulum.datetime(2019, 1, 31), True),
        (pendulum.datetime(2019, 2, 27), False),
        (pendulum.datetime(2019, 2, 28), True),
        (pendulum.datetime(2020, 2, 28), False),
        (pendulum.datetime(2020, 2, 29), True),
    ],
)
def test_is_month_end(dates):
    assert filters.is_month_end(dates[0]) is dates[1]
