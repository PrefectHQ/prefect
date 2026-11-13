from __future__ import annotations

import datetime
from datetime import timedelta
from typing import Callable
from zoneinfo import ZoneInfo

import pytest

import prefect.types._datetime


def _in_timezone(
    dt: datetime.datetime, tz: ZoneInfo | str
) -> prefect.types._datetime.DateTime | datetime.datetime:
    # On Python 3.12 and earlier, pendulum drops a plain ZoneInfo tzinfo on
    # arithmetic, so `now("UTC") - delta` would come back naive.  Converting
    # through `create_datetime_instance` gives pendulum's own timezone there,
    # the same kind of object the real `now(tz)` returns.
    return prefect.types._datetime.create_datetime_instance(
        dt.astimezone(ZoneInfo(getattr(tz, "name", tz)))
    )


@pytest.fixture
def frozen_time(
    monkeypatch: pytest.MonkeyPatch,
) -> prefect.types._datetime.DateTime | datetime.datetime:
    frozen = prefect.types._datetime.now("UTC")

    def frozen_time(tz: ZoneInfo | str | None = None):
        if tz is None:
            return frozen
        else:
            return _in_timezone(frozen, tz)

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
            return _in_timezone(clock, tz)

    monkeypatch.setattr(prefect.types._datetime, "now", nowish)

    return advance
