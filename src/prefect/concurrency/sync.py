from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional, TypeVar, Union

from typing_extensions import Literal

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.types._datetime import now
from prefect.utilities.asyncutils import run_coro_as_sync

from ._asyncio import (
    aacquire_concurrency_slots,
    arelease_concurrency_slots,
)
from ._events import (
    emit_concurrency_acquisition_events,
    emit_concurrency_release_events,
)

T = TypeVar("T")


def _release_concurrency_slots(
    names: list[str], slots: int, occupancy_seconds: float
) -> list[MinimalConcurrencyLimitResponse]:
    result = run_coro_as_sync(
        arelease_concurrency_slots(names, slots, occupancy_seconds)
    )
    return result


def _acquire_concurrency_slots(
    names: list[str],
    slots: int,
    mode: Literal["concurrency", "rate_limit"] = "concurrency",
    timeout_seconds: Optional[float] = None,
    create_if_missing: Optional[bool] = None,
    max_retries: Optional[int] = None,
    strict: bool = False,
) -> list[MinimalConcurrencyLimitResponse]:
    result = run_coro_as_sync(
        aacquire_concurrency_slots(
            names, slots, mode, timeout_seconds, create_if_missing, max_retries, strict
        )
    )
    return result


@contextmanager
def concurrency(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    strict: bool = False,
    create_if_missing: Optional[bool] = None,
) -> Generator[None, None, None]:
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
    if not names:
        yield
        return

    names = names if isinstance(names, list) else [names]

    limits: list[MinimalConcurrencyLimitResponse] = _acquire_concurrency_slots(
        names,
        occupy,
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        strict=strict,
        max_retries=max_retries,
    )
    acquisition_time = now("UTC")
    emitted_events = emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_period = now("UTC") - acquisition_time
        _release_concurrency_slots(names, occupy, occupancy_period.total_seconds())
        emit_concurrency_release_events(limits, occupy, emitted_events)


def rate_limit(
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

    limits = _acquire_concurrency_slots(
        names,
        occupy,
        mode="rate_limit",
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        strict=strict,
    )
    emit_concurrency_acquisition_events(limits, occupy)
