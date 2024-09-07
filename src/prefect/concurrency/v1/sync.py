from contextlib import contextmanager
from typing import (
    Generator,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

import pendulum

from ...client.schemas.responses import MinimalConcurrencyLimitResponse

try:
    from pendulum import Interval
except ImportError:
    # pendulum < 3
    from pendulum.period import Period as Interval  # type: ignore

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

    limits: List[MinimalConcurrencyLimitResponse] = _acquire_concurrency_slots(
        names,
        timeout_seconds=timeout_seconds,
        task_run_id=task_run_id,
        _sync=True,
    )
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, task_run_id)

    try:
        yield
    finally:
        occupancy_period = cast(Interval, pendulum.now("UTC") - acquisition_time)
        _release_concurrency_slots(
            names,
            task_run_id,
            occupancy_period.total_seconds(),
            _sync=True,
        )
        _emit_concurrency_release_events(limits, emitted_events, task_run_id)
