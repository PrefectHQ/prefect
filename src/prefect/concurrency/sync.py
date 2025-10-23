from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Optional, TypeVar, Union

from ._events import (
    emit_concurrency_acquisition_events,
)
from ._sync import (
    acquire_concurrency_slots as _acquire_concurrency_slots,
)
from ._sync import (
    concurrency as _concurrency_internal,
)

if TYPE_CHECKING:
    from prefect.client.schemas.objects import ConcurrencyLeaseHolder

T = TypeVar("T")


@contextmanager
def concurrency(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    lease_duration: float = 300,
    strict: bool = False,
    holder: "Optional[ConcurrencyLeaseHolder]" = None,
) -> Generator[None, None, None]:
    """A context manager that acquires and releases concurrency slots from the
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
    with _concurrency_internal(
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


def rate_limit(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
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

    limits = _acquire_concurrency_slots(
        names,
        occupy,
        mode="rate_limit",
        timeout_seconds=timeout_seconds,
        strict=strict,
    )
    emit_concurrency_acquisition_events(limits, occupy)
