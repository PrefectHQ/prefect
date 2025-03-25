from datetime import timedelta
from typing import Callable, Optional, Union

import pytest
from pendulum import DateTime
from pendulum.tz.timezone import Timezone

import prefect.types._datetime


@pytest.fixture
def frozen_time(monkeypatch: pytest.MonkeyPatch) -> prefect.types._datetime.DateTime:
    frozen = prefect.types._datetime.now("UTC")

    def frozen_time(tz: Optional[Union[str, Timezone]] = None):
        if tz is None:
            return frozen
        return frozen.in_timezone(tz)

    monkeypatch.setattr(prefect.types._datetime, "now", frozen_time)
    monkeypatch.setattr(prefect.types._datetime.DateTime, "now", frozen_time)
    return frozen


@pytest.fixture
def advance_time(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], DateTime]:
    clock = prefect.types._datetime.now("UTC")

    def advance(amount: timedelta):
        nonlocal clock
        clock += amount
        return clock

    def nowish(tz: Optional[Union[str, Timezone]] = None):
        # each time this is called, advance by 1 microsecond so that time is moving
        # forward bit-by-bit to avoid everything appearing to happen all at once
        advance(timedelta(microseconds=1))

        if tz is None:
            return clock

        return clock.in_timezone(tz)

    monkeypatch.setattr(DateTime, "now", nowish)

    return advance
