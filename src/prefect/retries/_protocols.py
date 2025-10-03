from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Literal

from typing_extensions import Protocol

if TYPE_CHECKING:
    from ._dataclasses import AttemptState

HookType = Literal[
    "before_attempt", "on_success", "on_failure", "before_wait", "after_wait"
]


class WaitTimeProvider(Protocol):
    """
    Protocol for callables that produce a wait time given the previous and next
    AttemptState.

    Args:
        prev: The previous AttemptState, or None if this is the first attempt.
        next: The next AttemptState (the one about to be run).

    Returns:
        The wait time as a timedelta, seconds (int/float), or None.
    """

    def __call__(
        self, prev: AttemptState | None, next: AttemptState
    ) -> datetime.timedelta | int | float | None: ...


class AttemptHook(Protocol):
    """
    Protocol for callables that are called at various points in the attempt lifecycle.

    Args:
        state: The AttemptState.
    """

    def __call__(self, state: AttemptState) -> None: ...

    __name__: str


class AsyncAttemptHook(Protocol):
    """
    Protocol for async callables that are called at various points in the attempt
    lifecycle.

    Args:
        state: The AttemptState.
    """

    async def __call__(self, state: AttemptState) -> None: ...

    __name__: str
