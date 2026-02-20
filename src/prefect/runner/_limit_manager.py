from typing import Any
from uuid import UUID, uuid4

import anyio

from prefect.logging import get_logger


class LimitManager:
    """Wraps `anyio.CapacityLimiter` with a token-based acquire/release API.

    When limit=None: `acquire()` returns a sentinel UUID, `release()` is a no-op,
    and `has_slots_available()` returns False (preserving Runner's current behavior).

    When limit is set: `acquire()` returns a UUID token that must be passed back to
    `release()`. Using a fresh `uuid4()` per call eliminates the duplicate-borrower
    RuntimeError that required a guard in the old runner code.
    """

    def __init__(self, *, limit: int | None) -> None:
        self._logger = get_logger("runner.limit_manager")
        self._limit = limit
        self._limiter: anyio.CapacityLimiter | None = None

    async def __aenter__(self) -> "LimitManager":
        if self._limit is not None:
            self._limiter = anyio.CapacityLimiter(self._limit)
        return self

    async def __aexit__(self, *_: Any) -> None:
        self._limiter = None

    def acquire(self) -> UUID:
        """Acquire a concurrency slot and return a release token.

        Returns a UUID token on success. Raises `anyio.WouldBlock` if at capacity.
        When limit=None, returns a sentinel UUID (no limiter interaction).
        """
        token = uuid4()
        if self._limiter is None:
            self._logger.debug(
                "No concurrency limit configured, returning sentinel token"
            )
            return token
        self._limiter.acquire_on_behalf_of_nowait(token)
        self._logger.debug(
            "Limit slot acquired (token=%s, borrowed=%s/%s)",
            token,
            self._limiter.borrowed_tokens,
            self._limiter.total_tokens,
        )
        return token

    def release(self, token: UUID) -> None:
        """Release a previously acquired slot.

        When limit=None (sentinel token), this is a no-op.
        """
        if self._limiter is None:
            return
        self._limiter.release_on_behalf_of(token)
        self._logger.debug("Limit slot released (token=%s)", token)

    def has_slots_available(self) -> bool:
        """Return True if concurrency slots are available.

        Returns False when limit=None, preserving current Runner behavior.
        """
        if not self._limiter:
            return False
        return self._limiter.available_tokens > 0
