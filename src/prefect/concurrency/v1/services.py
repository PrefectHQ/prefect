import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import httpx
from starlette import status
from typing_extensions import Unpack

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.services import FutureQueueService
from prefect.client.orchestration import get_client
from prefect.utilities.timeout import timeout_async

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


class ConcurrencySlotAcquisitionServiceError(Exception):
    """Raised when an error occurs while acquiring concurrency slots."""


class ConcurrencySlotAcquisitionService(
    FutureQueueService[Unpack[tuple[UUID, Optional[float]]], httpx.Response]
):
    def __init__(self, concurrency_limit_names: frozenset[str]) -> None:
        super().__init__(concurrency_limit_names)
        self._client: PrefectClient
        self.concurrency_limit_names: list[str] = sorted(list(concurrency_limit_names))

    @asynccontextmanager
    async def _lifespan(self) -> AsyncGenerator[None, None]:
        async with get_client() as client:
            self._client = client
            yield

    async def acquire(
        self, task_run_id: UUID, timeout_seconds: Optional[float] = None
    ) -> httpx.Response:
        with timeout_async(seconds=timeout_seconds):
            while True:
                try:
                    return await self._client.increment_v1_concurrency_slots(
                        task_run_id=task_run_id,
                        names=self.concurrency_limit_names,
                    )
                except httpx.HTTPStatusError as exc:
                    if not exc.response.status_code == status.HTTP_423_LOCKED:
                        raise

                    retry_after = exc.response.headers.get("Retry-After")
                    if retry_after:
                        retry_after = float(retry_after)
                        await asyncio.sleep(retry_after)
                    else:
                        # We received a 423 but no Retry-After header. This
                        # should indicate that the server told us to abort
                        # because the concurrency limit is set to 0, i.e.
                        # effectively disabled.
                        try:
                            reason = exc.response.json()["detail"]
                        except (JSONDecodeError, KeyError):
                            logger.error(
                                "Failed to parse response from concurrency limit 423 Locked response: %s",
                                exc.response.content,
                            )
                            reason = "Concurrency limit is locked (server did not specify the reason)"
                        raise ConcurrencySlotAcquisitionServiceError(reason) from exc
