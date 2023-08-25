import asyncio
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, List, Literal, Optional, Union

import httpx
import pendulum

from prefect import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.settings import PREFECT_CLIENT_RETRY_JITTER_FACTOR
from prefect.utilities.math import bounded_poisson_interval, clamped_poisson_interval

from .events import (
    _emit_concurrency_acquisition_events,
    _emit_concurrency_release_events,
)


async def wait_for_successful_response(
    fn: Callable[..., Awaitable[httpx.Response]],
    *args,
    max_retry_seconds: int = 30,
    retryable_status_codes: Optional[List[int]] = None,
    **kwargs,
) -> httpx.Response:
    """Given a callable `fn`, call it with `*args` and `**kwargs` and retry on
    `retryable_status_codes` until a 2xx status code is returned.

    When retrying a request it will first look for a `Retry-After` header and
    use that value, if that fails it'll fall back to an exponential backoff
    with a max of `max_retry_seconds` seconds."""

    jitter_factor = PREFECT_CLIENT_RETRY_JITTER_FACTOR.value()
    try_count = 0

    retryable_status_codes = retryable_status_codes or [429, 502, 503]

    while True:
        retry_seconds = None
        try_count += 1
        try:
            response = await fn(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in retryable_status_codes:
                try:
                    retry_after = float(exc.response.headers["Retry-After"])
                    retry_seconds = bounded_poisson_interval(
                        retry_after, retry_after * (1.0 + jitter_factor)
                    )
                except Exception:
                    retry_seconds = clamped_poisson_interval(
                        min(2**try_count, max_retry_seconds)
                    )
                await asyncio.sleep(int(retry_seconds))
            else:
                raise exc
        else:
            return response


async def acquire_concurrency_slots(
    names: List[str],
    slots: int,
    mode: Union[Literal["concurrency"], Literal["rate_limit"]] = "concurrency",
) -> List[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        response = await wait_for_successful_response(
            client.increment_concurrency_slots,
            names=names,
            slots=slots,
            mode=mode,
            retryable_status_codes=[423],
        )
        return _response_to_minimal_concurrency_limit_response(response)


async def release_concurrency_slots(
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


@asynccontextmanager
async def concurrency(names: Union[str, List[str]], occupy: int = 1):
    names = names if isinstance(names, list) else [names]

    limits = await acquire_concurrency_slots(names, occupy)
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_seconds: float = (
            pendulum.now("UTC") - acquisition_time
        ).total_seconds()
        await release_concurrency_slots(names, occupy, occupancy_seconds)
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
    limits = await acquire_concurrency_slots(names, occupy, mode="rate_limit")
    _emit_concurrency_acquisition_events(limits, occupy)
