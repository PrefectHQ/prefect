from collections.abc import Generator
from contextlib import contextmanager
from typing import Optional, TypeVar, Union
from uuid import UUID

from typing_extensions import Literal

from prefect.client.schemas.responses import (
    ConcurrencyLimitWithLeaseResponse,
    MinimalConcurrencyLimitResponse,
)
from prefect.concurrency._leases import maintain_concurrency_lease
from prefect.utilities.asyncutils import run_coro_as_sync

from ._asyncio import (
    aacquire_concurrency_slots,
    aacquire_concurrency_slots_with_lease,
    arelease_concurrency_slots_with_lease,
)
from ._events import (
    emit_concurrency_acquisition_events,
    emit_concurrency_release_events,
)

T = TypeVar("T")


def _release_concurrency_slots_with_lease(lease_id: UUID) -> None:
    run_coro_as_sync(arelease_concurrency_slots_with_lease(lease_id))


def _acquire_concurrency_slots(
    names: list[str],
    slots: int,
    mode: Literal["concurrency", "rate_limit"] = "concurrency",
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    strict: bool = False,
) -> list[MinimalConcurrencyLimitResponse]:
    result = run_coro_as_sync(
        aacquire_concurrency_slots(
            names, slots, mode, timeout_seconds, max_retries, strict
        )
    )
    return result


def _acquire_concurrency_slots_with_lease(
    names: list[str],
    slots: int,
    mode: Literal["concurrency", "rate_limit"] = "concurrency",
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    lease_duration: float = 300,
    strict: bool = False,
) -> ConcurrencyLimitWithLeaseResponse:
    result = run_coro_as_sync(
        aacquire_concurrency_slots_with_lease(
            names, slots, mode, timeout_seconds, max_retries, lease_duration, strict
        )
    )
    return result


@contextmanager
def concurrency(
    names: Union[str, list[str]],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    lease_duration: float = 300,
    strict: bool = False,
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

    acquisition_response = _acquire_concurrency_slots_with_lease(
        names,
        occupy,
        timeout_seconds=timeout_seconds,
        strict=strict,
        lease_duration=lease_duration,
        max_retries=max_retries,
    )
    emitted_events = emit_concurrency_acquisition_events(
        acquisition_response.limits, occupy
    )

    try:
        with maintain_concurrency_lease(
            acquisition_response.lease_id,
            lease_duration,
            raise_on_lease_renewal_failure=strict,
        ):
            yield
    finally:
        _release_concurrency_slots_with_lease(acquisition_response.lease_id)
        emit_concurrency_release_events(
            acquisition_response.limits, occupy, emitted_events
        )


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
