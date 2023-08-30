import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from typing import (
    FrozenSet,
    Tuple,
)

import httpx
from fastapi import status

from prefect import get_client
from prefect._internal.concurrency import logger
from prefect._internal.concurrency.services import QueueService
from prefect.client.orchestration import PrefectClient


class ConcurrencySlotAcquisitionService(QueueService):
    def __init__(self, concurrency_limit_names: FrozenSet[str]):
        super().__init__(concurrency_limit_names)
        self._client: PrefectClient
        self.concurrency_limit_names = sorted(list(concurrency_limit_names))

    @asynccontextmanager
    async def _lifespan(self):
        async with get_client() as client:
            self._client = client
            yield

    async def _handle(self, item: Tuple[int, str, concurrent.futures.Future]):
        occupy, mode, future = item
        try:
            response = await self.acquire_slots(occupy, mode)
        except Exception as exc:
            # If the request to the increment endpoint fails in a non-standard
            # way, we need to set the future's result so that the caller can
            # handle the exception and then re-raise.
            future.set_result(exc)
            raise exc
        else:
            future.set_result(response)

    async def acquire_slots(self, slots: int, mode: str) -> httpx.Response:
        while True:
            try:
                response = await self._client.increment_concurrency_slots(
                    names=self.concurrency_limit_names, slots=slots, mode=mode
                )
            except Exception as exc:
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == status.HTTP_423_LOCKED
                ):
                    retry_after = float(exc.response.headers["Retry-After"])
                    await asyncio.sleep(retry_after)
                else:
                    raise exc
            else:
                return response

    def send(self, item: Tuple[int, str]):
        with self._lock:
            if self._stopped:
                raise RuntimeError("Cannot put items in a stopped service instance.")

            logger.debug("Service %r enqueing item %r", self, item)
            future = concurrent.futures.Future()

            occupy, mode = item
            self._queue.put_nowait((occupy, mode, future))

        return future
