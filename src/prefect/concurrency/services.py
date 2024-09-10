import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    AsyncGenerator,
    FrozenSet,
    Optional,
    Tuple,
)

import httpx
from starlette import status

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.services import QueueService
from prefect.client.orchestration import get_client
from prefect.utilities.timeout import timeout_async

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


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
            int,
            str,
            Optional[float],
            concurrent.futures.Future,
            Optional[bool],
            Optional[int],
        ],
    ) -> None:
        occupy, mode, timeout_seconds, future, create_if_missing, max_retries = item
        try:
            response = await self.acquire_slots(
                occupy, mode, timeout_seconds, create_if_missing, max_retries
            )
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
        slots: int,
        mode: str,
        timeout_seconds: Optional[float] = None,
        create_if_missing: Optional[bool] = None,
        max_retries: Optional[int] = None,
    ) -> httpx.Response:
        with timeout_async(seconds=timeout_seconds):
            while True:
                try:
                    response = await self._client.increment_concurrency_slots(
                        names=self.concurrency_limit_names,
                        slots=slots,
                        mode=mode,
                        create_if_missing=create_if_missing,
                    )
                except Exception as exc:
                    if (
                        isinstance(exc, httpx.HTTPStatusError)
                        and exc.response.status_code == status.HTTP_423_LOCKED
                    ):
                        if max_retries is not None and max_retries <= 0:
                            raise exc
                        retry_after = float(exc.response.headers["Retry-After"])
                        await asyncio.sleep(retry_after)
                        if max_retries is not None:
                            max_retries -= 1
                    else:
                        raise exc
                else:
                    return response

    def send(
        self, item: Tuple[int, str, Optional[float], Optional[bool], Optional[int]]
    ) -> concurrent.futures.Future:
        with self._lock:
            if self._stopped:
                raise RuntimeError("Cannot put items in a stopped service instance.")

            logger.debug("Service %r enqueuing item %r", self, item)
            future: concurrent.futures.Future = concurrent.futures.Future()

            occupy, mode, timeout_seconds, create_if_missing, max_retries = item
            self._queue.put_nowait(
                (occupy, mode, timeout_seconds, future, create_if_missing, max_retries)
            )

        return future
