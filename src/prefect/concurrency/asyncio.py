from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional, Union

import anyio

from prefect.types._datetime import now

from ._asyncio import (
    AcquireConcurrencySlotTimeoutError as AcquireConcurrencySlotTimeoutError,
)
from ._asyncio import ConcurrencySlotAcquisitionError as ConcurrencySlotAcquisitionError
from ._asyncio import aacquire_concurrency_slots, arelease_concurrency_slots
from ._events import (
    emit_concurrency_acquisition_events,
    emit_concurrency_release_events,
)
from .context import ConcurrencyContext


@asynccontextmanager
async def concurrency(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    create_if_missing: Optional[bool] = None,
    strict: bool = False,
) -> AsyncGenerator[None, None]:
    """A context manager that acquires and releases concurrency slots from the
    given concurrency limits.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and hold from each limit.
        timeout_seconds: The number of seconds to wait for the slots to be acquired before
            raising a `TimeoutError`. A timeout of `None` will wait indefinitely.
        max_retries: The maximum number of retries to acquire the concurrency slots.
        strict: A boolean specifying whether to raise an error if the concurrency limit does not exist.
            Defaults to `False`.

    Raises:
        TimeoutError: If the slots are not acquired within the given timeout.
        ConcurrencySlotAcquisitionError: If the concurrency limit does not exist and `strict` is `True`.

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
    if not names:
        yield
        return

    names = names if isinstance(names, list) else [names]

    limits = await aacquire_concurrency_slots(
        names,
        occupy,
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        max_retries=max_retries,
        strict=strict,
    )
    acquisition_time = now("UTC")
    emitted_events = emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_period = now("UTC") - acquisition_time
        try:
            await arelease_concurrency_slots(
                names, occupy, occupancy_period.total_seconds()
            )
        except anyio.get_cancelled_exc_class():
            # The task was cancelled before it could release the slots. Add the
            # slots to the cleanup list so they can be released when the
            # concurrency context is exited.
            if ctx := ConcurrencyContext.get():
                ctx.cleanup_slots.append(
                    (names, occupy, occupancy_period.total_seconds())
                )

        emit_concurrency_release_events(limits, occupy, emitted_events)


async def rate_limit(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    create_if_missing: Optional[bool] = None,
    strict: bool = False,
) -> None:
    """Block execution until an `occupy` number of slots of the concurrency
    limits given in `names` are acquired. Requires that all given concurrency
    limits have a slot decay.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and hold from each limit.
        timeout_seconds: The number of seconds to wait for the slots to be acquired before
            raising a `TimeoutError`. A timeout of `None` will wait indefinitely.
        strict: A boolean specifying whether to raise an error if the concurrency limit does not exist.
            Defaults to `False`.

    Raises:
        TimeoutError: If the slots are not acquired within the given timeout.
        ConcurrencySlotAcquisitionError: If the concurrency limit does not exist and `strict` is `True`.
    """
    if not names:
        return

    names = names if isinstance(names, list) else [names]

    limits = await aacquire_concurrency_slots(
        names,
        occupy,
        mode="rate_limit",
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        strict=strict,
    )
    emit_concurrency_acquisition_events(limits, occupy)
