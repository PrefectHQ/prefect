import asyncio
from contextlib import asynccontextmanager
from typing import List, Literal, Union

import httpx
import pendulum

from prefect import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse

from .events import (
    _emit_concurrency_acquisition_events,
    _emit_concurrency_release_events,
)
from .services import ConcurrencySlotAcquisitionService


class ConcurrencySlotAcquisitionError(Exception):
    """Raised when an unhandlable occurs while acquiring concurrency slots."""


@asynccontextmanager
async def concurrency(names: Union[str, List[str]], occupy: int = 1):
    names = names if isinstance(names, list) else [names]

    limits = await _acquire_concurrency_slots(names, occupy)
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_seconds: float = (
            pendulum.now("UTC") - acquisition_time
        ).total_seconds()
        await _release_concurrency_slots(names, occupy, occupancy_seconds)
        _emit_concurrency_release_events(limits, occupy, emitted_events)


async def rate_limit(names: Union[str, List[str]], occupy: int = 1):
    """Block execution until an `occupy` number of slots of the concurrency
    limits given in `names` are acquired. Requires that all given concurrency
    limits have a slot decay.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and holf from each limit.
    """
    names = names if isinstance(names, list) else [names]
    limits = await _acquire_concurrency_slots(names, occupy, mode="rate_limit")
    _emit_concurrency_acquisition_events(limits, occupy)


async def _acquire_concurrency_slots(
    names: List[str],
    slots: int,
    mode: Union[Literal["concurrency"], Literal["rate_limit"]] = "concurrency",
) -> List[MinimalConcurrencyLimitResponse]:
    service = ConcurrencySlotAcquisitionService.instance(frozenset(names))
    future = service.send((slots, mode))
    response_or_exception = await asyncio.wrap_future(future)

    if isinstance(response_or_exception, Exception):
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
    return [MinimalConcurrencyLimitResponse.parse_obj(obj_) for obj_ in response.json()]
