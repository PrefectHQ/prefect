import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional, TypeVar, Union
from uuid import UUID

from prefect.types._datetime import now

from ._asyncio import acquire_concurrency_slots, release_concurrency_slots
from ._events import (
    emit_concurrency_acquisition_events,
    emit_concurrency_release_events,
)

T = TypeVar("T")


@contextmanager
def concurrency(
    names: Union[str, list[str]],
    task_run_id: UUID,
    timeout_seconds: Optional[float] = None,
) -> Generator[None, None, None]:
    """
    A context manager that acquires and releases concurrency slots from the
    given concurrency limits.

    Args:
        names: The names of the concurrency limits to acquire.
        task_run_id: The task run ID acquiring the limits.
        timeout_seconds: The number of seconds to wait to acquire the limits before
            raising a `TimeoutError`. A timeout of `None` will wait indefinitely.

    Raises:
        TimeoutError: If the limits are not acquired within the given timeout.

    Example:
    A simple example of using the sync `concurrency` context manager:
    ```python
    from prefect.concurrency.v1.sync import concurrency

    def resource_heavy():
        with concurrency("test"):
            print("Resource heavy task")

    def main():
        resource_heavy()
    ```
    """
    if not names:
        yield
        return

    names = names if isinstance(names, list) else [names]

    force = {"_sync": True}
    result = acquire_concurrency_slots(
        names, timeout_seconds=timeout_seconds, task_run_id=task_run_id, **force
    )
    assert not asyncio.iscoroutine(result)
    limits = result
    acquisition_time = now("UTC")
    emitted_events = emit_concurrency_acquisition_events(limits, task_run_id)

    try:
        yield
    finally:
        occupancy_period = now("UTC") - acquisition_time
        release_concurrency_slots(
            names, task_run_id, occupancy_period.total_seconds(), **force
        )
        emit_concurrency_release_events(limits, emitted_events, task_run_id)
