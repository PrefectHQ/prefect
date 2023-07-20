from typing import List, Literal, Union
from contextlib import contextmanager

from prefect import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.events import Event, RelatedResource, emit_event
from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.event_loop import get_running_loop


async def acquire_concurrency_slots(
    names: List[str], slots: int
) -> List[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        return await client.acquire_concurrency_slots(names=names, slots=slots)


async def release_concurrency_slots(
    names: List[str], slots: int
) -> List[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        return await client.release_concurrency_slots(names=names, slots=slots)


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
def concurrency(names: Union[str, List[str]], slots: int = 1):
    if isinstance(names, str):
        names = [names]

    limits = run_async_function(acquire_concurrency_slots, names, slots)

    concurrency_limit_events = {}

    for limit in limits:
        event = emit_concurrency_event("acquired", limit, limits, slots)
        concurrency_limit_events[limit.id] = event

    try:
        yield
    finally:
        run_async_function(release_concurrency_slots, names, slots)
    for limit in limits:
        emit_concurrency_event(
            "released", limit, limits, slots, concurrency_limit_events[limit.id]
        )


def run_async_function(fn, *args, **kwargs):
    loop = get_running_loop()
    call = create_call(fn, *args, **kwargs)

    if loop is not None:
        return from_sync.call_soon_in_loop_thread(call).result()
    else:
        return call()
