import asyncio
from typing import Optional
from uuid import UUID

import httpx

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse

from .services import ConcurrencySlotAcquisitionService


class ConcurrencySlotAcquisitionError(Exception):
    """Raised when an unhandlable occurs while acquiring concurrency slots."""


class AcquireConcurrencySlotTimeoutError(TimeoutError):
    """Raised when acquiring a concurrency slot times out."""


async def aacquire_concurrency_slots(
    names: list[str],
    task_run_id: UUID,
    timeout_seconds: Optional[float] = None,
) -> list[MinimalConcurrencyLimitResponse]:
    """
    Acquire concurrency slots for the given task run.

    Args:
        names: The names of the concurrency limits to acquire slots for.
        task_run_id: The ID of the task run acquiring the slots.
        timeout_seconds: The maximum number of seconds to wait for the slots
            to be acquired.

    Returns:
        A list of concurrency limit responses.

    Raises:
        AcquireConcurrencySlotTimeoutError: If the slots are not acquired within
            the timeout.
        ConcurrencySlotAcquisitionError: If the slots cannot be acquired.
    """
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


@async_dispatch(aacquire_concurrency_slots)
def acquire_concurrency_slots(
    names: list[str],
    task_run_id: UUID,
    timeout_seconds: Optional[float] = None,
) -> list[MinimalConcurrencyLimitResponse]:
    """
    Acquire concurrency slots for the given task run.

    Args:
        names: The names of the concurrency limits to acquire slots for.
        task_run_id: The ID of the task run acquiring the slots.
        timeout_seconds: The maximum number of seconds to wait for the slots
            to be acquired.

    Returns:
        A list of concurrency limit responses.

    Raises:
        AcquireConcurrencySlotTimeoutError: If the slots are not acquired within
            the timeout.
        ConcurrencySlotAcquisitionError: If the slots cannot be acquired.
    """
    service = ConcurrencySlotAcquisitionService.instance(frozenset(names))
    future = service.send((task_run_id, timeout_seconds))
    try:
        response = future.result()
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


async def arelease_concurrency_slots(
    names: list[str], task_run_id: UUID, occupancy_seconds: float
) -> list[MinimalConcurrencyLimitResponse]:
    """
    Release concurrency slots for the given task run.

    Args:
        names: The names of the concurrency limits to release slots for.
        task_run_id: The ID of the task run releasing the slots.
        occupancy_seconds: The number of seconds the slots were occupied.

    Returns:
        A list of concurrency limit responses.
    """
    async with get_client() as client:
        response = await client.decrement_v1_concurrency_slots(
            names=names,
            task_run_id=task_run_id,
            occupancy_seconds=occupancy_seconds,
        )
        return _response_to_concurrency_limit_response(response)


@async_dispatch(arelease_concurrency_slots)
def release_concurrency_slots(
    names: list[str], task_run_id: UUID, occupancy_seconds: float
) -> list[MinimalConcurrencyLimitResponse]:
    """
    Release concurrency slots for the given task run.

    Args:
        names: The names of the concurrency limits to release slots for.
        task_run_id: The ID of the task run releasing the slots.
        occupancy_seconds: The number of seconds the slots were occupied.

    Returns:
        A list of concurrency limit responses.
    """
    with get_client(sync_client=True) as client:
        response = client.decrement_v1_concurrency_slots(
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
