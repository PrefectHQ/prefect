import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from json import JSONDecodeError
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    FrozenSet,
    Optional,
    Tuple,
)
from uuid import UUID

import httpx
from starlette import status

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.services import QueueService
from prefect.client.orchestration import get_client
from prefect.utilities.timeout import timeout_async

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


class ConcurrencySlotAcquisitionServiceError(Exception):
    """Raised when an error occurs while acquiring concurrency slots."""


class ConcurrencySlotAcquisitionService(QueueService):
    def __init__(self, concurrency_limit_names: FrozenSet[str]):
        super().__init__(concurrency_limit_names)
        self._client: "PrefectClient"
        self.concurrency_limit_names = sorted(list(concurrency_limit_names))

    @asynccontextmanager
    async def _lifespan(self) -> AsyncGenerator[None, None]:
        async with get_client() as client:
            self._client = client
            yield

    async def _handle(
        self,
        item: Tuple[
            UUID,
            concurrent.futures.Future,
            Optional[float],
        ],
    ) -> None:
        task_run_id, future, timeout_seconds = item
        try:
            response = await self.acquire_slots(task_run_id, timeout_seconds)
        except Exception as exc:
            # If the request to the increment endpoint fails in a non-standard
            # way, we need to set the future's result so that the caller can
            # handle the exception and then re-raise.
            future.set_result(exc)
            raise exc
        else:
            future.set_result(response)

    async def acquire_slots(
        self,
        task_run_id: UUID,
        timeout_seconds: Optional[float] = None,
    ) -> httpx.Response:
        with timeout_async(seconds=timeout_seconds):
            while True:
                try:
                    response = await self._client.increment_v1_concurrency_slots(
                        task_run_id=task_run_id,
                        names=self.concurrency_limit_names,
                    )
                except Exception as exc:
                    if (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code == status.HTTP_423_LOCKED
                    ):
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
                            raise ConcurrencySlotAcquisitionServiceError(
                                reason
                            ) from exc

                    else:
                        raise exc  # type: ignore
                else:
                    return response

    def send(self, item: Tuple[UUID, Optional[float]]) -> concurrent.futures.Future:
        with self._lock:
            if self._stopped:
                raise RuntimeError("Cannot put items in a stopped service instance.")

            logger.debug("Service %r enqueuing item %r", self, item)
            future: concurrent.futures.Future = concurrent.futures.Future()

            task_run_id, timeout_seconds = item
            self._queue.put_nowait((task_run_id, future, timeout_seconds))

        return future
