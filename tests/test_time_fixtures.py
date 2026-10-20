from datetime import datetime, timedelta, timezone

import pytest

import prefect.types._datetime


@pytest.mark.parametrize("clock_fixture", ["frozen_time", "advance_time"])
def test_patched_now_stays_aware_under_arithmetic(
    request: pytest.FixtureRequest, clock_fixture: str
):
    request.getfixturevalue(clock_fixture)
    current = prefect.types._datetime.now("UTC")

    earlier = current - timedelta(minutes=1)

    assert earlier.tzinfo is not None
    assert earlier == datetime.fromtimestamp(
        current.timestamp(), timezone.utc
    ) - timedelta(minutes=1)
