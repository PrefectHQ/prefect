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


def test_is_month_start_or_specific_day():
    years = {
        1971: {"month": 2, "day": 21},  # Before start of UTC
        1972: {"month": 6, "day": 11},  # Start of UTC
        1992: {"month": 6, "day": 7},  # Near past
        2020: {"month": 9, "day": 13},  # Relative present
        2525: {"month": 12, "day": 2},  # Distant future
    }

    months = range(1, 12)
    days_week = range(0, 6)

    def test_first_day_of_every_month():
        filter_fn = filters.is_month_start_or_specific_day()

        for month in months:
            for year in years:
                assert filter_fn(pendulum.datetime(year=year, month=month, day=1))
                assert not filter_fn(pendulum.datetime(year=year, month=month, day=2))

    def test_day_of_week(day_of_week):
        filter_fn = filters.is_month_start_or_specific_day(day_of_week=day_of_week)

        for year in years:
            month = years[year].month
            day = (
                years[year].day + day_of_week
            )  # day of the week also acts as an offset for each day, which starts at Sunday (0)
            next_day = day + 1

            assert filter_fn(pendulum.datetime(year=year, month=month, day=day))
            assert not filter_fn(
                pendulum.datetime(year=year, month=month, day=next_day)
            )

    test_first_day_of_every_month()

    for day in days_week:
        test_day_of_week(day)


def test_is_month_end_or_specific_day():
    years = {
        1971: {"month": 2, "day": 21},  # Before start of UTC
        1972: {"month": 6, "day": 11},  # Start of UTC
        1992: {"month": 6, "day": 7},  # Near past
        2020: {"month": 9, "day": 13},  # Relative present
        2525: {"month": 12, "day": 2},  # Distant future
    }

    months = range(1, 12)
    days_week = range(0, 6)

    def test_last_day_of_every_month():
        filter_fn = filters.is_month_start_or_specific_day()

        for month in months:
            for year in years:
                assert filter_fn(
                    pendulum.datetime(year=year, month=month).end_of("month")
                )
                assert not filter_fn(pendulum.datetime(year=year, month=month, day=15))

    def test_day_of_week(day_of_week):
        filter_fn = filters.is_month_start_or_specific_day(day_of_week=day_of_week)

        for year in years:
            month = years[year].month
            day = (
                years[year].day + day_of_week
            )  # day of the week also acts as an offset for each day, which starts at Sunday (0)
            next_day = day + 1

            assert filter_fn(pendulum.datetime(year=year, month=month, day=day))
            assert not filter_fn(
                pendulum.datetime(year=year, month=month, day=next_day)
            )

    test_last_day_of_every_month()

    for day in days_week:
        test_day_of_week(day)