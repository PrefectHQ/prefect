from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Optional, Union

from ._asyncio import (
    AcquireConcurrencySlotTimeoutError as AcquireConcurrencySlotTimeoutError,
)
from ._asyncio import ConcurrencySlotAcquisitionError as ConcurrencySlotAcquisitionError
from ._asyncio import (
    aacquire_concurrency_slots,
)
from ._asyncio import (
    concurrency as _concurrency_internal,
)
from ._events import (
    emit_concurrency_acquisition_events,
)

if TYPE_CHECKING:
    from prefect.client.schemas.objects import ConcurrencyLeaseHolder


@asynccontextmanager
async def concurrency(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    lease_duration: float = 300,
    strict: bool = False,
    holder: "Optional[ConcurrencyLeaseHolder]" = None,
) -> AsyncGenerator[None, None]:
    """A
    context manager that acquires and releases concurrency slots from the
    given concurrency limits.

    Args:
        names: The names of the concurrency limits to acquire slots from.
        occupy: The number of slots to acquire and hold from each limit.
        timeout_seconds: The number of seconds to wait for the slots to be acquired before
            raising a `TimeoutError`. A timeout of `None` will wait indefinitely.
        max_retries: The maximum number of retries to acquire the concurrency slots.
        lease_duration: The duration of the lease for the acquired slots in seconds.
        strict: A boolean specifying whether to raise an error if the concurrency limit does not exist.
            Defaults to `False`.
        holder: A dictionary containing information about the holder of the concurrency slots.
            Typically includes 'type' and 'id' keys.

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
    async with _concurrency_internal(
        names=names,
        occupy=occupy,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        lease_duration=lease_duration,
        strict=strict,
        holder=holder,
        suppress_warnings=False,
    ):
        yield


async def rate_limit(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    strict: bool = False,
) -> None:
    """
    Block execution until an `occupy` number of slots of the concurrency
    limits given in `names` are acquired.

    Requires that all given concurrency limits have a slot decay.

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
        names=names,
        slots=occupy,
        mode="rate_limit",
        timeout_seconds=timeout_seconds,
        strict=strict,
    )
    emit_concurrency_acquisition_events(limits, occupy)
