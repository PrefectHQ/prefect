import pytest
from prefect.orion.api.schedules import IntervalSchedule
from pydantic import ValidationError
from datetime import timedelta
from pendulum import datetime, now


class TestCreateIntervalSchedule:
    def test_interval_is_required(self):
        with pytest.raises(ValidationError, match="(field required)"):
            IntervalSchedule()

    @pytest.mark.parametrize("minutes", [-1, 0])
    def test_interval_must_be_positive(self, minutes):
        with pytest.raises(ValidationError, match="(interval must be positive)"):
            IntervalSchedule(interval=timedelta(minutes=minutes))

    def test_default_anchor_is_now(self):
        dt = now()
        schedule = IntervalSchedule(interval=timedelta(days=1))
        assert dt < schedule.anchor < now()

    @pytest.mark.parametrize("x", [[], [1], [3, 6, 9, 12]])
    def test_valid_months(self, x):
        schedule = IntervalSchedule(interval=timedelta(days=1), months=x)
        assert schedule.months == set(x)

    @pytest.mark.parametrize("x", [[-1], 1, [0], [3, 13]])
    def test_invalid_months(self, x):
        with pytest.raises(ValidationError):
            IntervalSchedule(interval=timedelta(days=1), months=x)

    @pytest.mark.parametrize("x", [[], [1], [15, 31], [-1], [-1, 1], [-28]])
    def test_valid_days_of_month(self, x):
        schedule = IntervalSchedule(interval=timedelta(days=1), days_of_month=x)
        assert schedule.days_of_month == set(x)

    @pytest.mark.parametrize("x", [1, [0], [-32, 1], [1, 32]])
    def test_invalid_days_of_month(self, x):
        with pytest.raises(ValidationError):
            IntervalSchedule(interval=timedelta(days=1), days_of_month=x)

    @pytest.mark.parametrize("x", [[], [0], [0, 1, 2, 3, 4]])
    def test_valid_days_of_week(self, x):
        schedule = IntervalSchedule(interval=timedelta(days=1), days_of_week=x)
        assert schedule.days_of_week == set(x)

    @pytest.mark.parametrize("x", [[-1], 1, [3, 7]])
    def test_invalid_days_of_week(self, x):
        with pytest.raises(ValidationError):
            IntervalSchedule(interval=timedelta(days=1), days_of_week=x)

    @pytest.mark.parametrize("x", [[], [0], [0, 1, 2, 3, 4]])
    def test_valid_hours_of_day(self, x):
        schedule = IntervalSchedule(interval=timedelta(days=1), hours_of_day=x)
        assert schedule.hours_of_day == set(x)

    @pytest.mark.parametrize("x", [[-1], 1, [1, 24]])
    def test_invalid_hours_of_day(self, x):
        with pytest.raises(ValidationError):
            IntervalSchedule(interval=timedelta(days=1), hours_of_day=x)

    @pytest.mark.parametrize("x", [[], [0], [0, 1, 2, 3, 4]])
    def test_valid_minutes_of_hour(self, x):
        schedule = IntervalSchedule(interval=timedelta(days=1), minutes_of_hour=x)
        assert schedule.minutes_of_hour == set(x)

    @pytest.mark.parametrize("x", [[-1], 1, [3, 60]])
    def test_invalid_minutes_of_hour(self, x):
        with pytest.raises(ValidationError):
            IntervalSchedule(interval=timedelta(days=1), minutes_of_hour=x)


class TestIntervalSchedule:
    @pytest.mark.parametrize(
        "start_date",
        [
            datetime(2018, 1, 1),
            datetime(2021, 2, 2),
            datetime(2025, 3, 3),
        ],
    )
    def test_get_dates_from_start_date(self, start_date):
        schedule = IntervalSchedule(
            interval=timedelta(days=1), anchor=datetime(2021, 1, 1)
        )
        dates = schedule.get_dates(n=5, start=start_date)
        assert dates == [start_date.add(days=i) for i in range(5)]

    @pytest.mark.parametrize("n", [1, 2, 5])
    def test_get_n_dates(self, n):
        schedule = IntervalSchedule(interval=timedelta(days=1))
        assert len(schedule.get_dates(n=n)) == n

    def test_get_dates_from_anchor(self):
        schedule = IntervalSchedule(
            interval=timedelta(days=1), anchor=datetime(2020, 2, 2, 23, 35)
        )
        dates = schedule.get_dates(n=5, start=datetime(2021, 7, 1))
        assert dates == [datetime(2021, 7, 1, 23, 35).add(days=i) for i in range(5)]

    def test_get_dates_from_future_anchor(self):
        schedule = IntervalSchedule(
            interval=timedelta(hours=17), anchor=datetime(2030, 2, 2, 5, 24)
        )
        dates = schedule.get_dates(n=5, start=datetime(2021, 7, 1))
        assert dates == [
            datetime(2021, 7, 1, 7, 24).add(hours=i * 17) for i in range(5)
        ]

    def test_months_filter(self):
        schedule = IntervalSchedule(
            interval=timedelta(days=10),
            anchor=datetime(2021, 1, 1),
            months=[1, 3],
        )
        dates = schedule.get_dates(n=10, start=datetime(2021, 1, 1))
        assert dates == [
            datetime(2021, 1, 1),
            datetime(2021, 1, 11),
            datetime(2021, 1, 21),
            datetime(2021, 1, 31),
            datetime(2021, 3, 2),
            datetime(2021, 3, 12),
            datetime(2021, 3, 22),
            datetime(2022, 1, 6),
            datetime(2022, 1, 16),
            datetime(2022, 1, 26),
        ]

    def test_days_of_month_filter(self):
        schedule = IntervalSchedule(
            interval=timedelta(days=1),
            anchor=datetime(2021, 1, 1),
            months=[2, 4, 6, 8, 10, 12],
            days_of_month=[1, 5],
        )
        dates = schedule.get_dates(n=5, start=datetime(2021, 2, 2))
        assert dates == [
            datetime(2021, 2, 5),
            datetime(2021, 4, 1),
            datetime(2021, 4, 5),
            datetime(2021, 6, 1),
            datetime(2021, 6, 5),
        ]

    def test_negative_days_of_month_filter(self):
        schedule = IntervalSchedule(
            interval=timedelta(days=1),
            anchor=datetime(2021, 1, 1),
            days_of_month=[1, -5],
        )
        dates = schedule.get_dates(n=8, start=datetime(2021, 1, 1))
        assert dates == [
            datetime(2021, 1, 1),
            datetime(2021, 1, 27),
            datetime(2021, 2, 1),
            datetime(2021, 2, 24),
            datetime(2021, 3, 1),
            datetime(2021, 3, 27),
            datetime(2021, 4, 1),
            datetime(2021, 4, 26),
        ]

    def test_days_of_week_filter(self):
        schedule = IntervalSchedule(
            interval=timedelta(days=1),
            anchor=datetime(2021, 1, 1, 12),
            days_of_week=[2, 4],
        )
        dates = schedule.get_dates(n=5, start=datetime(2021, 1, 1))
        assert dates == [
            datetime(2021, 1, 1, 12),
            datetime(2021, 1, 6, 12),
            datetime(2021, 1, 8, 12),
            datetime(2021, 1, 13, 12),
            datetime(2021, 1, 15, 12),
        ]

    def test_hours_of_day_filter(self):
        schedule = IntervalSchedule(
            interval=timedelta(hours=1),
            anchor=datetime(2021, 1, 1),
            hours_of_day=[11, 12, 13],
        )
        dates = schedule.get_dates(n=5, start=datetime(2021, 1, 1))
        assert dates == [
            datetime(2021, 1, 1, 11),
            datetime(2021, 1, 1, 12),
            datetime(2021, 1, 1, 13),
            datetime(2021, 1, 2, 11),
            datetime(2021, 1, 2, 12),
        ]

    def test_minutes_of_hour_filter(self):
        schedule = IntervalSchedule(
            interval=timedelta(minutes=5),
            anchor=datetime(2021, 1, 1),
            minutes_of_hour=list(range(0, 15)),
        )
        dates = schedule.get_dates(n=5, start=datetime(2021, 1, 1))
        assert dates == [
            datetime(2021, 1, 1, 0),
            datetime(2021, 1, 1, 0, 5),
            datetime(2021, 1, 1, 0, 10),
            datetime(2021, 1, 1, 1, 0),
            datetime(2021, 1, 1, 1, 5),
        ]
