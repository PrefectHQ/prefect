from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID

import anyio

from prefect.concurrency.v1._asyncio import (
    acquire_concurrency_slots,
    release_concurrency_slots,
)
from prefect.concurrency.v1._events import (
    emit_concurrency_acquisition_events,
    emit_concurrency_release_events,
)
from prefect.concurrency.v1.context import ConcurrencyContext
from prefect.types._datetime import now

from ._asyncio import (
    AcquireConcurrencySlotTimeoutError as AcquireConcurrencySlotTimeoutError,
)
from ._asyncio import ConcurrencySlotAcquisitionError as ConcurrencySlotAcquisitionError


@asynccontextmanager
async def concurrency(
    names: Union[str, list[str]],
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

    names_normalized: list[str] = names if isinstance(names, list) else [names]

    acquire_slots = acquire_concurrency_slots(
        names_normalized,
        task_run_id=task_run_id,
        timeout_seconds=timeout_seconds,
    )
    if TYPE_CHECKING:
        assert not isinstance(acquire_slots, list)
    limits = await acquire_slots
    acquisition_time = now("UTC")
    emitted_events = emit_concurrency_acquisition_events(limits, task_run_id)

    try:
        yield
    finally:
        occupancy_period = now("UTC") - acquisition_time
        try:
            release_slots = release_concurrency_slots(
                names_normalized, task_run_id, occupancy_period.total_seconds()
            )
            if TYPE_CHECKING:
                assert not isinstance(release_slots, list)
            await release_slots
        except anyio.get_cancelled_exc_class():
            # The task was cancelled before it could release the slots. Add the
            # slots to the cleanup list so they can be released when the
            # concurrency context is exited.
            if ctx := ConcurrencyContext.get():
                ctx.cleanup_slots.append(
                    (names_normalized, occupancy_period.total_seconds(), task_run_id)
                )

        emit_concurrency_release_events(limits, emitted_events, task_run_id)
