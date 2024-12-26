import asyncio
from typing import Optional
from uuid import UUID

import httpx

from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.utilities.asyncutils import sync_compatible

from .services import ConcurrencySlotAcquisitionService


class ConcurrencySlotAcquisitionError(Exception):
    """Raised when an unhandlable occurs while acquiring concurrency slots."""


class AcquireConcurrencySlotTimeoutError(TimeoutError):
    """Raised when acquiring a concurrency slot times out."""


@sync_compatible
async def acquire_concurrency_slots(
    names: list[str],
    task_run_id: UUID,
    timeout_seconds: Optional[float] = None,
) -> list[MinimalConcurrencyLimitResponse]:
    service = ConcurrencySlotAcquisitionService.instance(frozenset(names))
    future = service.send((task_run_id, timeout_seconds))
    try:
        response = await asyncio.wrap_future(future)
    except TimeoutError as timeout:
        raise AcquireConcurrencySlotTimeoutError(
            f"Attempt to acquire concurrency limits timed out after {timeout_seconds} second(s)"
        ) from timeout
    except Exception as exc:
        raise ConcurrencySlotAcquisitionError(
            f"Unable to acquire concurrency limits {names!r}"
        ) from exc
    else:
        return _response_to_concurrency_limit_response(response)


@sync_compatible
async def release_concurrency_slots(
    names: list[str], task_run_id: UUID, occupancy_seconds: float
) -> list[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        response = await client.decrement_v1_concurrency_slots(
            names=names,
            task_run_id=task_run_id,
            occupancy_seconds=occupancy_seconds,
        )
        return _response_to_concurrency_limit_response(response)


def _response_to_concurrency_limit_response(
    response: httpx.Response,
) -> list[MinimalConcurrencyLimitResponse]:
    data: list[MinimalConcurrencyLimitResponse] = response.json() or []
    return [
        MinimalConcurrencyLimitResponse.model_validate(limit) for limit in data if data
    ]
