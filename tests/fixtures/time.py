import datetime
from datetime import timedelta
from typing import Callable, Optional, Union
from zoneinfo import ZoneInfo

import pytest

from prefect.types._datetime import DateTime, Timezone, now


@pytest.fixture
def frozen_time(monkeypatch: pytest.MonkeyPatch) -> DateTime | datetime.datetime:
    frozen = now("UTC")

    def frozen_time(tz: Optional[Union[str, Timezone]] = None):
        if tz is None:
            return frozen
        if isinstance(frozen, DateTime):
            return frozen.in_timezone(tz)
        else:
            return frozen.astimezone(
                tz=ZoneInfo(tz.name if isinstance(tz, Timezone) else tz)
            )

    monkeypatch.setattr(DateTime, "now", frozen_time)
    return frozen


@pytest.fixture
def advance_time(monkeypatch: pytest.MonkeyPatch) -> Callable[[timedelta], DateTime]:
    clock = now("UTC")

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
