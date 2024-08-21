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
from uuid import UUID

import httpx
from pydantic import ValidationError
from starlette import status

from prefect._internal.concurrency import logger
from prefect._internal.concurrency.services import QueueService
from prefect.client.orchestration import get_client
from prefect.client.schemas import OrchestrationResult
from prefect.exceptions import Abort
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
                                response = OrchestrationResult.model_validate(
                                    exc.response.json()
                                )
                                raise Abort(response.details.reason) from exc
                            except ValidationError as exc:
                                # We're supposed to get a valid orchestration result here,
                                # containing the result for the abort. We didn't, so we don't
                                # know why the server told us to abort, but we do know we have
                                # to abort.
                                logger.error(
                                    "Failed to validate v1 slot acquisition response"
                                )
                                raise Abort(
                                    "Concurrency slot acquisition failed"
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
