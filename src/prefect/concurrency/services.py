import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Optional

import httpx
from starlette import status
from typing_extensions import TypeAlias, Unpack

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.services import FutureQueueService
from prefect.client.orchestration import get_client
from prefect.utilities.timeout import timeout_async

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient

_Item: TypeAlias = tuple[int, str, Optional[float], Optional[int]]


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
        mode: str,
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
