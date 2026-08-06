"""Select the event loop implementation Prefect creates.

Opt-in via `PREFECT_EVENT_LOOP`: `asyncio` (default), `zuvloop`, or `uvloop`.
Selecting a loop that is not installed raises immediately rather than silently
falling back, and the environment variable is inherited by child processes so
workers and spawned flow runs make the same choice.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Coroutine
from typing import TypeVar

R = TypeVar("R")

LoopFactory = Callable[[], asyncio.AbstractEventLoop]

_ENV_VAR = "PREFECT_EVENT_LOOP"


def get_loop_factory() -> LoopFactory | None:
    """Return the configured loop factory, or None for stdlib asyncio."""
    choice = os.environ.get(_ENV_VAR, "asyncio")
    if choice == "asyncio":
        return None
    if choice == "zuvloop":
        try:
            from zuvloop import new_event_loop
        except ImportError as exc:
            raise RuntimeError(
                f"{_ENV_VAR}=zuvloop but zuvloop is not installed"
            ) from exc
        return new_event_loop
    if choice == "uvloop":
        try:
            from uvloop import new_event_loop
        except ImportError as exc:
            raise RuntimeError(
                f"{_ENV_VAR}=uvloop but uvloop is not installed"
            ) from exc
        return new_event_loop
    raise RuntimeError(
        f"unknown {_ENV_VAR} value {choice!r}; expected asyncio, zuvloop, or uvloop"
    )


def uvicorn_loop() -> str:
    """The value for `uvicorn.Config(loop=...)` honoring the selection."""
    choice = os.environ.get(_ENV_VAR, "asyncio")
    if choice == "asyncio":
        # prevent uvloop from setting global policy
        return "asyncio"
    get_loop_factory()  # fail loud if unavailable
    if choice == "zuvloop":
        return "zuvloop:new_event_loop"
    return "uvloop:new_event_loop"


def run_coro(coro: Coroutine[object, object, R]) -> R:
    """`asyncio.run()` honoring the configured loop factory."""
    factory = get_loop_factory()
    if factory is None:
        return asyncio.run(coro)
    with asyncio.Runner(loop_factory=factory) as runner:
        return runner.run(coro)
