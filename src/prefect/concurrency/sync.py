from contextlib import contextmanager
from typing import List, Union

import pendulum

from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.event_loop import get_running_loop
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse

from .asyncio import (
    _acquire_concurrency_slots,
    _release_concurrency_slots,
)
from .events import (
    _emit_concurrency_acquisition_events,
    _emit_concurrency_release_events,
)


@contextmanager
def concurrency(names: Union[str, List[str]], occupy: int = 1):
    names = names if isinstance(names, list) else [names]

    limits: List[MinimalConcurrencyLimitResponse] = _call_async_function_from_sync(
        _acquire_concurrency_slots, names, occupy
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
            _release_concurrency_slots, names, occupy, occupancy_seconds
        )
        _emit_concurrency_release_events(limits, occupy, emitted_events)


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
        _acquire_concurrency_slots, names, occupy, mode="rate_limit"
    )
    _emit_concurrency_acquisition_events(limits, occupy)


def _call_async_function_from_sync(fn, *args, **kwargs):
    loop = get_running_loop()
    call = create_call(fn, *args, **kwargs)

    if loop is not None:
        return from_sync.call_soon_in_loop_thread(call).result()
    else:
        return call()
