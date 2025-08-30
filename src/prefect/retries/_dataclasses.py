from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Phase(Enum):
    """Enum representing the current phase of an attempt."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


@dataclass
class AttemptState:
    """
    A dataclass that represents the state of an attempt.

    Args:
        attempt: The attempt number.
        exception: The exception that occurred, if any.
        result: The result of the attempt, if any. Ellipsis is used as a sentinel
            to indicate that a result has not been set yet.
        wait_seconds: The number of seconds waited after the attempt.
        phase: The current phase of the attempt.
    """

    attempt: int
    exception: BaseException | None = None
    result: Any = ...
    wait_seconds: float | None = None
    phase: Phase = Phase.PENDING
