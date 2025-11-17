import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Literal, Optional

import httpx
from starlette import status
from typing_extensions import TypeAlias, Unpack

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.services import FutureQueueService
from prefect.client.orchestration import get_client
from prefect.utilities.timeout import timeout_async

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import ConcurrencyLeaseHolder

_Item: TypeAlias = tuple[
    int, Literal["concurrency", "rate_limit"], Optional[float], Optional[int]
]

_ItemWithLease: TypeAlias = tuple[
    int,
    Literal["concurrency", "rate_limit"],
    Optional[float],
    Optional[int],
    float,
    bool,
    Optional["ConcurrencyLeaseHolder"],
]


class ConcurrencySlotAcquisitionService(
    FutureQueueService[Unpack[_Item], httpx.Response]
):
    def __init__(self, concurrency_limit_names: frozenset[str]):
        super().__init__(concurrency_limit_names)
        self._client: PrefectClient
        self.concurrency_limit_names: list[str] = sorted(list(concurrency_limit_names))

    @asynccontextmanager
    async def _lifespan(self) -> AsyncGenerator[None, None]:
        async with get_client() as client:
            self._client = client
            yield

    async def acquire(
        self,
        slots: int,
        mode: Literal["concurrency", "rate_limit"],
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
    ) -> httpx.Response:
        with timeout_async(seconds=timeout_seconds):
            while True:
                try:
                    return await self._client.increment_concurrency_slots(
                        names=self.concurrency_limit_names,
                        slots=slots,
                        mode=mode,
                    )
                except httpx.HTTPStatusError as exc:
                    if not exc.response.status_code == status.HTTP_423_LOCKED:
                        raise

                    if max_retries is not None and max_retries <= 0:
                        raise exc
                    retry_after = float(exc.response.headers["Retry-After"])
                    logger.debug(
                        f"Unable to acquire concurrency slot. Retrying in {retry_after} second(s)."
                    )
                    await asyncio.sleep(retry_after)
                    if max_retries is not None:
                        max_retries -= 1


class ConcurrencySlotAcquisitionWithLeaseService(
    FutureQueueService[Unpack[_ItemWithLease], httpx.Response]
):
    """A service that acquires concurrency slots with leases.

    This service serializes acquisition attempts for a given set of limit names,
    preventing thundering herd issues when many tasks try to acquire slots simultaneously.
    Each unique set of limit names gets its own singleton service instance.

    Args:
        concurrency_limit_names: A frozenset of concurrency limit names to acquire slots from.
    """

    def __init__(self, concurrency_limit_names: frozenset[str]):
        super().__init__(concurrency_limit_names)
        self._client: PrefectClient
        self.concurrency_limit_names: list[str] = sorted(list(concurrency_limit_names))

    @asynccontextmanager
    async def _lifespan(self) -> AsyncGenerator[None, None]:
        async with get_client() as client:
            self._client = client
            yield

    async def acquire(
        self,
        slots: int,
        mode: Literal["concurrency", "rate_limit"],
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        lease_duration: float = 300,
        strict: bool = False,
        holder: Optional["ConcurrencyLeaseHolder"] = None,
    ) -> httpx.Response:
        """Acquire concurrency slots with a lease, with retry logic for 423 responses.

        Args:
            slots: Number of slots to acquire
            mode: Either "concurrency" or "rate_limit"
            timeout_seconds: Optional timeout for the entire acquisition attempt
            max_retries: Maximum number of retries on 423 LOCKED responses
            lease_duration: Duration of the lease in seconds
            strict: Whether to raise errors for missing limits
            holder: Optional holder information for the lease

        Returns:
            HTTP response from the server

        Raises:
            httpx.HTTPStatusError: If the server returns an error other than 423 LOCKED
            TimeoutError: If acquisition times out
        """
        with timeout_async(seconds=timeout_seconds):
            while True:
                try:
                    return await self._client.increment_concurrency_slots_with_lease(
                        names=self.concurrency_limit_names,
                        slots=slots,
                        mode=mode,
                        lease_duration=lease_duration,
                        holder=holder,
                    )
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != status.HTTP_423_LOCKED:
                        raise

                    if max_retries is not None and max_retries <= 0:
                        raise exc

                    retry_after = float(exc.response.headers["Retry-After"])
                    logger.debug(
                        f"Unable to acquire concurrency slot with lease for {self.concurrency_limit_names}. Retrying in {retry_after} second(s)."
                    )
                    await asyncio.sleep(retry_after)
                    if max_retries is not None:
                        max_retries -= 1
