from __future__ import annotations

import datetime
from datetime import timedelta
from typing import Callable
from zoneinfo import ZoneInfo

import pytest

import prefect.types._datetime


@pytest.fixture
def frozen_time(
    monkeypatch: pytest.MonkeyPatch,
) -> prefect.types._datetime.DateTime | datetime.datetime:
    frozen = prefect.types._datetime.now("UTC")

    def frozen_time(tz: ZoneInfo | str | None = None):
        if tz is None:
            return frozen
        else:
            return frozen.astimezone(tz=ZoneInfo(getattr(tz, "name", tz)))

    monkeypatch.setattr(prefect.types._datetime, "now", frozen_time)
    return frozen


@pytest.fixture
def advance_time(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[timedelta], prefect.types._datetime.DateTime]:
    clock = prefect.types._datetime.now("UTC")

    def advance(amount: timedelta):
        nonlocal clock
        clock += amount
        return clock

    def nowish(tz: ZoneInfo | str | None = None):
        # each time this is called, advance by 1 microsecond so that time is moving
        # forward bit-by-bit to avoid everything appearing to happen all at once
        advance(timedelta(microseconds=1))

        if tz is None:
            return clock
        else:
            return clock.astimezone(ZoneInfo(getattr(tz, "name", tz)))

    monkeypatch.setattr(prefect.types._datetime, "now", nowish)

    return advance
