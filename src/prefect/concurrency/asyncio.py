import asyncio
from contextlib import asynccontextmanager
from typing import List, Literal, Optional, Union, cast

import httpx
import pendulum

try:
    from pendulum import Interval
except ImportError:
    # pendulum < 3
    from pendulum.period import Period as Interval  # type: ignore

from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse

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
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
):
    """A context manager that acquires and releases concurrency slots from the
    given concurrency limits.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and hold from each limit.
        timeout_seconds: The number of seconds to wait for the slots to be acquired before
            raising a `TimeoutError`. A timeout of `None` will wait indefinitely.

    Raises:
        TimeoutError: If the slots are not acquired within the given timeout.

    Example:
    A simple example of using the async `concurrency` context manager:
    ```python
    from prefect.concurrency.asyncio import concurrency

    async def resource_heavy():
        async with concurrency("test", occupy=1):
            print("Resource heavy task")

    async def main():
        await resource_heavy()
    ```
    """
    names = names if isinstance(names, list) else [names]
    limits = await _acquire_concurrency_slots(
        names, occupy, timeout_seconds=timeout_seconds
    )
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_period = cast(Interval, (pendulum.now("UTC") - acquisition_time))
        await _release_concurrency_slots(
            names, occupy, occupancy_period.total_seconds()
        )
        _emit_concurrency_release_events(limits, occupy, emitted_events)


async def rate_limit(names: Union[str, List[str]], occupy: int = 1):
    """Block execution until an `occupy` number of slots of the concurrency
    limits given in `names` are acquired. Requires that all given concurrency
    limits have a slot decay.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and hold from each limit.
    """
    names = names if isinstance(names, list) else [names]
    limits = await _acquire_concurrency_slots(names, occupy, mode="rate_limit")
    _emit_concurrency_acquisition_events(limits, occupy)


async def _acquire_concurrency_slots(
    names: List[str],
    slots: int,
    mode: Union[Literal["concurrency"], Literal["rate_limit"]] = "concurrency",
    timeout_seconds: Optional[float] = None,
) -> List[MinimalConcurrencyLimitResponse]:
    service = ConcurrencySlotAcquisitionService.instance(frozenset(names))
    future = service.send((slots, mode, timeout_seconds))
    response_or_exception = await asyncio.wrap_future(future)

    if isinstance(response_or_exception, Exception):
        if isinstance(response_or_exception, TimeoutError):
            raise AcquireConcurrencySlotTimeoutError(
                f"Attempt to acquire concurrency slots timed out after {timeout_seconds} second(s)"
            ) from response_or_exception

        raise ConcurrencySlotAcquisitionError(
            f"Unable to acquire concurrency slots on {names!r}"
        ) from response_or_exception

    return _response_to_minimal_concurrency_limit_response(response_or_exception)


async def _release_concurrency_slots(
    names: List[str], slots: int, occupancy_seconds: float
) -> List[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        response = await client.release_concurrency_slots(
            names=names, slots=slots, occupancy_seconds=occupancy_seconds
        )
        return _response_to_minimal_concurrency_limit_response(response)


def _response_to_minimal_concurrency_limit_response(
    response: httpx.Response,
) -> List[MinimalConcurrencyLimitResponse]:
    return [
        MinimalConcurrencyLimitResponse.model_validate(obj_) for obj_ in response.json()
    ]
