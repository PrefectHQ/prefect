from contextlib import contextmanager
from typing import List, Optional, Union, cast

import pendulum

try:
    from pendulum import Interval
except ImportError:
    # pendulum < 3
    from pendulum.period import Period as Interval  # type: ignore

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
def concurrency(
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
    A simple example of using the sync `concurrency` context manager:
    ```python
    from prefect.concurrency.sync import concurrency

    def resource_heavy():
        with concurrency("test", occupy=1):
            print("Resource heavy task")

    def main():
        resource_heavy()
    ```
    """
    names = names if isinstance(names, list) else [names]

    limits: List[MinimalConcurrencyLimitResponse] = _call_async_function_from_sync(
        _acquire_concurrency_slots, names, occupy, timeout_seconds=timeout_seconds
    )
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_period = cast(Interval, pendulum.now("UTC") - acquisition_time)
        _call_async_function_from_sync(
            _release_concurrency_slots,
            names,
            occupy,
            occupancy_period.total_seconds(),
        )
        _emit_concurrency_release_events(limits, occupy, emitted_events)


def rate_limit(names: Union[str, List[str]], occupy: int = 1):
    """Block execution until an `occupy` number of slots of the concurrency
    limits given in `names` are acquired. Requires that all given concurrency
    limits have a slot decay.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and hold from each limit.
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
