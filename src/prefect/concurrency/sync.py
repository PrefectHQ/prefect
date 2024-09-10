from contextlib import contextmanager
from typing import (
    Generator,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)

import pendulum

try:
    from pendulum import Interval
except ImportError:
    # pendulum < 3
    from pendulum.period import Period as Interval  # type: ignore

from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse

from .asyncio import (
    _acquire_concurrency_slots,
    _release_concurrency_slots,
)
from .events import (
    _emit_concurrency_acquisition_events,
    _emit_concurrency_release_events,
)

T = TypeVar("T")


@contextmanager
def concurrency(
    names: Union[str, List[str]],
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

    limits: List[MinimalConcurrencyLimitResponse] = _acquire_concurrency_slots(
        names,
        occupy,
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        strict=strict,
        max_retries=max_retries,
        _sync=True,
    )
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_period = cast(Interval, pendulum.now("UTC") - acquisition_time)
        _release_concurrency_slots(
            names,
            occupy,
            occupancy_period.total_seconds(),
            _sync=True,
        )
        _emit_concurrency_release_events(limits, occupy, emitted_events)


def rate_limit(
    names: Union[str, List[str]],
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
        _sync=True,
    )
    _emit_concurrency_acquisition_events(limits, occupy)
