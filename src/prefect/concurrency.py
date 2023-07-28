import asyncio
from typing import Awaitable, Callable, List, Literal, Union
from contextlib import contextmanager

import httpx
import pendulum

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

                await asyncio.sleep(retry_seconds)
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


def emit_concurrency_event(
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
                "prefect.resource.role": "concurrency_limit",
            }
        )
        for limit in related_limits
    ]

    event = emit_event(
        f"prefect.concurrency-limit.{phase}",
        resource=resource,
        related=related,
        follows=follows,
    )
    return event


@contextmanager
def concurrency(names: Union[str, List[str]], occupy: int = 1):
    """A context manager to acquire, hold, and release concurrency slots of the
    concurrency limits given in `names`.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and holf from each limit.
    """

    if isinstance(names, str):
        names = [names]

    limits = call_async_function(acquire_concurrency_slots, names, occupy)

    concurrency_limit_events = {}

    for limit in limits:
        event = emit_concurrency_event("acquired", limit, limits, occupy)
        concurrency_limit_events[limit.id] = event

    acquisition_time = pendulum.now("UTC")

    try:
        yield
    finally:
        occupancy_seconds: float = (
            pendulum.now("UTC") - acquisition_time
        ).total_seconds()

        call_async_function(release_concurrency_slots, names, occupy, occupancy_seconds)
        for limit in limits:
            emit_concurrency_event(
                "released", limit, limits, occupy, concurrency_limit_events[limit.id]
            )


def rate_limit(names: Union[str, List[str]], occupy: int = 1):
    """Block execution until an `occupy` number of slots of the concurrency
    limits given in `names` are acquired. Requires that all given concurrency
    limits have a slot decay.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and holf from each limit.
    """

    if isinstance(names, str):
        names = [names]

    limits = call_async_function(
        acquire_concurrency_slots, names, occupy, mode="rate_limit"
    )

    for limit in limits:
        emit_concurrency_event("acquired", limit, limits, occupy)


def call_async_function(fn, *args, **kwargs):
    loop = get_running_loop()
    call = create_call(fn, *args, **kwargs)

    if loop is not None:
        return from_sync.call_soon_in_loop_thread(call).result()
    else:
        return call()


def _response_to_minimal_concurrency_limit_response(
    response: httpx.Response,
) -> List[MinimalConcurrencyLimitResponse]:
    return [MinimalConcurrencyLimitResponse.parse_obj(obj_) for obj_ in response.json()]
