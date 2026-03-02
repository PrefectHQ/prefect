from typing import Any
from uuid import UUID, uuid4

import anyio

from prefect.logging import get_logger


class LimitManager:
    """Wraps `anyio.CapacityLimiter` with a token-based acquire/release API.

    When limit=None: `acquire()` returns a sentinel UUID, `release()` is a no-op,
    and `has_slots_available()` returns True (unlimited capacity).

    When limit is set: `acquire()` returns a UUID token that must be passed back to
    `release()`. Using a fresh `uuid4()` per call eliminates the duplicate-borrower
    RuntimeError that required a guard in the old runner code.
    """

    def __init__(self, *, limit: int | None) -> None:
        self._logger = get_logger("runner.limit_manager")
        self._limit = limit
        self._limiter: anyio.CapacityLimiter | None = None
        self._started = False

    async def __aenter__(self) -> "LimitManager":
        if self._limit is not None:
            self._limiter = anyio.CapacityLimiter(self._limit)
        self._started = True
        return self

    async def __aexit__(self, *_: Any) -> None:
        self._limiter = None
        self._started = False

    def acquire(self) -> UUID:
        """Acquire a concurrency slot and return a release token.

        Returns a UUID token on success. Raises `anyio.WouldBlock` if at capacity.
        When limit=None, returns a sentinel UUID (no limiter interaction).
        """
        if not self._started and self._limit is not None:
            raise RuntimeError(
                "LimitManager must be entered as an async context manager"
                " before calling acquire()"
            )
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

    def acquire_for_flow_run(self, flow_run_id: UUID) -> bool:
        """Acquire a slot using flow_run_id as borrower identity.

        Returns True on success. Catches RuntimeError for duplicate
        borrowers (same flow_run_id already holding a slot) and
        anyio.WouldBlock (no capacity).
        """
        if self._limiter is None:
            return True
        try:
            self._limiter.acquire_on_behalf_of_nowait(flow_run_id)
            return True
        except RuntimeError as exc:
            if "already holding" in str(exc):
                return False
            raise
        except anyio.WouldBlock:
            return False

    def release_for_flow_run(self, flow_run_id: UUID) -> None:
        """Release a slot held by flow_run_id."""
        if self._limiter is not None:
            self._limiter.release_on_behalf_of(flow_run_id)

    def has_slots_available(self) -> bool:
        """Return True if concurrency slots are available.

        Returns True when limit=None (unlimited capacity).
        """
        if not self._limiter:
            return True
        return self._limiter.available_tokens > 0
