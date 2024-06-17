from datetime import timedelta
from typing import Callable, Optional, Union

import pendulum
import pytest
from pendulum import DateTime
from pendulum.tz.timezone import Timezone


@pytest.fixture
def frozen_time(monkeypatch: pytest.MonkeyPatch) -> pendulum.DateTime:
    frozen = pendulum.now("UTC")

    def frozen_time(tz: Optional[Union[str, Timezone]] = None):
        if tz is None:
            return frozen
        return frozen.in_timezone(tz)

    monkeypatch.setattr(pendulum, "now", frozen_time)
    return frozen


@pytest.fixture
def advance_time(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], DateTime]:
    clock = pendulum.now("UTC")

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

    monkeypatch.setattr(pendulum, "now", nowish)

    return advance
