from datetime import timedelta

import pendulum
import pytest

import prefect.schedules.adjustments as adjustments
import prefect.schedules.filters


@pytest.mark.parametrize(
    "interval",
    [
        timedelta(days=1),
        timedelta(seconds=0),
        timedelta(days=-1),
        timedelta(microseconds=1),
    ],
)
def test_add(interval):
    dt = pendulum.now()
    adjustment_fn = adjustments.add(interval)
    assert adjustment_fn(dt) == dt + interval


@pytest.mark.parametrize("dt", [pendulum.datetime(2019, 1, i) for i in range(1, 10)])
def test_next_weekday(dt):
    adjusted = adjustments.next_weekday(dt)
    if prefect.schedules.filters.is_weekday(dt):
        assert adjusted is dt
    else:
        assert adjusted > dt and adjusted.weekday() == 0
