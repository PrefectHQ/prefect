import asyncio
from uuid import UUID
from functools import wraps
from typing import Awaitable, Callable, Dict, List, Literal, Optional, Union
from contextlib import asynccontextmanager, contextmanager

import httpx
import pendulum

from prefect._internal.concurrency.threads import in_global_loop
from prefect import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.events import Event, RelatedResource, emit_event
from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.event_loop import get_running_loop
from prefect.utilities.math import bounded_poisson_interval, clamped_poisson_interval
from prefect.settings import PREFECT_CLIENT_RETRY_JITTER_FACTOR


async def wait_for_successful_response(
    fn: Callable[..., Awaitable[httpx.Response]],
    *args,
    max_retry_seconds=30,
    retryable_status_codes=[429, 502, 503],
    **kwargs,
) -> httpx.Response:
    """Given a callable `fn`, call it with `*args` and `**kwargs` and retry on
    `retryable_status_codes` until a 2xx status code is returned.

    When retrying a request it will first look for a `Retry-After` header and
    use that value, if that fails it'll fall back to an exponential backoff
    with a max of `max_retry_seconds` seconds."""

    jitter_factor = PREFECT_CLIENT_RETRY_JITTER_FACTOR.value()
    try_count = 0

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


@asynccontextmanager
async def aconcurrency(names: Union[str, List[str]], occupy: int = 1):
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


@contextmanager
def concurrency(names: Union[str, List[str]], occupy: int = 1):
    names = names if isinstance(names, list) else [names]

    limits: List[MinimalConcurrencyLimitResponse] = _call_async_function_from_sync(
        acquire_concurrency_slots, names, occupy
    )
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_seconds: float = (
            pendulum.now("UTC") - acquisition_time
        ).total_seconds()
        _call_async_function_from_sync(
            release_concurrency_slots, names, occupy, occupancy_seconds
        )
        _emit_concurrency_release_events(limits, occupy, emitted_events)


async def arate_limit(names: Union[str, List[str]], occupy: int = 1):
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


def rate_limit(names: Union[str, List[str]], occupy: int = 1):
    """Block execution until an `occupy` number of slots of the concurrency
    limits given in `names` are acquired. Requires that all given concurrency
    limits have a slot decay.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and holf from each limit.
    """
    names = names if isinstance(names, list) else [names]
    limits = _call_async_function_from_sync(
        acquire_concurrency_slots, names, occupy, mode="rate_limit"
    )
    _emit_concurrency_acquisition_events(limits, occupy)


def _call_async_function_from_sync(fn, *args, **kwargs):
    loop = get_running_loop()
    call = create_call(fn, *args, **kwargs)

    if loop is not None:
        return from_sync.call_soon_in_loop_thread(call).result()
    else:
        return call()


def _emit_concurrency_event(
    phase: Union[Literal["acquired"], Literal["released"]],
    primary_limit: MinimalConcurrencyLimitResponse,
    related_limits: List[MinimalConcurrencyLimitResponse],
    slots: int,
    follows: Union[Event, None] = None,
) -> Union[Event, None]:
    resource = {
        "prefect.resource.id": f"prefect.concurrency-limit.{primary_limit.id}",
        "prefect.resource.name": primary_limit.name,
        "slots-acquired": slots,
        "limit": primary_limit.limit,
    }

    related = [
        RelatedResource(
            __root__={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit.id}",
                "prefect.resource.role": "concurrency-limit",
            }
        )
        for limit in related_limits
        if limit.id != primary_limit.id
    ]

    return emit_event(
        f"prefect.concurrency-limit.{phase}",
        resource=resource,
        related=related,
        follows=follows,
    )


def _emit_concurrency_acquisition_events(
    limits: List[MinimalConcurrencyLimitResponse],
    occupy: int,
) -> Dict[UUID, Optional[Event]]:
    events = {}
    for limit in limits:
        event = _emit_concurrency_event("acquired", limit, limits, occupy)
        events[limit.id] = event

    return events


def _emit_concurrency_release_events(
    limits: List[MinimalConcurrencyLimitResponse],
    occupy: int,
    events: Dict[UUID, Optional[Event]],
):
    for limit in limits:
        _emit_concurrency_event("released", limit, limits, occupy, events[limit.id])


def _response_to_minimal_concurrency_limit_response(
    response: httpx.Response,
) -> List[MinimalConcurrencyLimitResponse]:
    return [MinimalConcurrencyLimitResponse.parse_obj(obj_) for obj_ in response.json()]
