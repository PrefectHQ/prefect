from __future__ import annotations

import datetime
from datetime import timedelta
from typing import Callable, Optional, Union
from zoneinfo import ZoneInfo

import pytest

import prefect.types._datetime


@pytest.fixture
def frozen_time(
    monkeypatch: pytest.MonkeyPatch,
) -> prefect.types._datetime.DateTime | datetime.datetime:
    frozen = prefect.types._datetime.now("UTC")

    def frozen_time(tz: Optional[Union[str, prefect.types._datetime.Timezone]] = None):
        if tz is None:
            return frozen
        if isinstance(frozen, prefect.types._datetime.DateTime):
            return frozen.in_timezone(tz)
        else:
            return frozen.astimezone(
                tz=ZoneInfo(
                    tz.name if isinstance(tz, prefect.types._datetime.Timezone) else tz
                )
            )

    monkeypatch.setattr(prefect.types._datetime.DateTime, "now", frozen_time)
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

    def nowish(tz: Optional[Union[str, prefect.types._datetime.Timezone]] = None):
        # each time this is called, advance by 1 microsecond so that time is moving
        # forward bit-by-bit to avoid everything appearing to happen all at once
        advance(timedelta(microseconds=1))

        if tz is None:
            return clock

        if isinstance(tz, prefect.types._datetime.Timezone):
            return clock.astimezone(ZoneInfo(tz.name))
        else:
            return clock.astimezone(ZoneInfo(tz))

    monkeypatch.setattr(prefect.types._datetime.DateTime, "now", nowish)
    monkeypatch.setattr(prefect.types._datetime, "now", nowish)

    return advance
