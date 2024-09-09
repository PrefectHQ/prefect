import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Optional, Union, cast
from uuid import UUID

import anyio
import httpx
import pendulum

from ...client.schemas.responses import MinimalConcurrencyLimitResponse

try:
    from pendulum import Interval
except ImportError:
    # pendulum < 3
    from pendulum.period import Period as Interval  # type: ignore

from prefect.client.orchestration import get_client
from prefect.utilities.asyncutils import sync_compatible

from .context import ConcurrencyContext
from .events import (
    _emit_concurrency_acquisition_events,
    _emit_concurrency_release_events,
)
from .services import ConcurrencySlotAcquisitionService


class ConcurrencySlotAcquisitionError(Exception):
    """Raised when an unhandlable occurs while acquiring concurrency slots."""


class AcquireConcurrencySlotTimeoutError(TimeoutError):
    """Raised when acquiring a concurrency slot times out."""


@asynccontextmanager
async def concurrency(
    names: Union[str, List[str]],
    task_run_id: UUID,
    timeout_seconds: Optional[float] = None,
) -> AsyncGenerator[None, None]:
    """A context manager that acquires and releases concurrency slots from the
    given concurrency limits.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        task_run_id: The name of the task_run_id that is incrementing the slots.
        timeout_seconds: The number of seconds to wait for the slots to be acquired before
            raising a `TimeoutError`. A timeout of `None` will wait indefinitely.

    Raises:
        TimeoutError: If the slots are not acquired within the given timeout.

    Example:
    A simple example of using the async `concurrency` context manager:
    ```python
    from prefect.concurrency.v1.asyncio import concurrency

    async def resource_heavy():
        async with concurrency("test", task_run_id):
            print("Resource heavy task")

    async def main():
        await resource_heavy()
    ```
    """
    if not names:
        yield
        return

    names_normalized: List[str] = names if isinstance(names, list) else [names]

    limits = await _acquire_concurrency_slots(
        names_normalized,
        task_run_id=task_run_id,
        timeout_seconds=timeout_seconds,
    )
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, task_run_id)

    try:
        yield
    finally:
        occupancy_period = cast(Interval, (pendulum.now("UTC") - acquisition_time))
        try:
            await _release_concurrency_slots(
                names_normalized, task_run_id, occupancy_period.total_seconds()
            )
        except anyio.get_cancelled_exc_class():
            # The task was cancelled before it could release the slots. Add the
            # slots to the cleanup list so they can be released when the
            # concurrency context is exited.
            if ctx := ConcurrencyContext.get():
                ctx.cleanup_slots.append(
                    (names_normalized, occupancy_period.total_seconds(), task_run_id)
                )

        _emit_concurrency_release_events(limits, emitted_events, task_run_id)


@sync_compatible
async def _acquire_concurrency_slots(
    names: List[str],
    task_run_id: UUID,
    timeout_seconds: Optional[float] = None,
) -> List[MinimalConcurrencyLimitResponse]:
    service = ConcurrencySlotAcquisitionService.instance(frozenset(names))
    future = service.send((task_run_id, timeout_seconds))
    response_or_exception = await asyncio.wrap_future(future)

    if isinstance(response_or_exception, Exception):
        if isinstance(response_or_exception, TimeoutError):
            raise AcquireConcurrencySlotTimeoutError(
                f"Attempt to acquire concurrency limits timed out after {timeout_seconds} second(s)"
            ) from response_or_exception

        raise ConcurrencySlotAcquisitionError(
            f"Unable to acquire concurrency limits {names!r}"
        ) from response_or_exception

    return _response_to_concurrency_limit_response(response_or_exception)


@sync_compatible
async def _release_concurrency_slots(
    names: List[str],
    task_run_id: UUID,
    occupancy_seconds: float,
) -> List[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        response = await client.decrement_v1_concurrency_slots(
            names=names,
            task_run_id=task_run_id,
            occupancy_seconds=occupancy_seconds,
        )
        return _response_to_concurrency_limit_response(response)


def _response_to_concurrency_limit_response(
    response: httpx.Response,
) -> List[MinimalConcurrencyLimitResponse]:
    data = response.json() or []
    return [
        MinimalConcurrencyLimitResponse.model_validate(limit) for limit in data if data
    ]
