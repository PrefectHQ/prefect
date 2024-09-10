import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List, Literal, Optional, Union, cast

import anyio
import httpx
import pendulum

from prefect._internal.compatibility.deprecated import deprecated_parameter

try:
    from pendulum import Interval
except ImportError:
    # pendulum < 3
    from pendulum.period import Period as Interval  # type: ignore

from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.logging.loggers import get_run_logger
from prefect.utilities.asyncutils import sync_compatible

from .context import ConcurrencyContext
from .events import (
    _emit_concurrency_acquisition_events,
    _emit_concurrency_release_events,
)
from .services import ConcurrencySlotAcquisitionService


class ConcurrencySlotAcquisitionError(Exception):
    """Raised when an unhandlable occurs while acquiring concurrency slots."""


class AcquireConcurrencySlotTimeoutError(TimeoutError):
    """Raised when acquiring a concurrency slot times out."""


@asynccontextmanager
async def concurrency(
    names: Union[str, List[str]],
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

    limits = await _acquire_concurrency_slots(
        names,
        occupy,
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        max_retries=max_retries,
        strict=strict,
    )
    acquisition_time = pendulum.now("UTC")
    emitted_events = _emit_concurrency_acquisition_events(limits, occupy)

    try:
        yield
    finally:
        occupancy_period = cast(Interval, (pendulum.now("UTC") - acquisition_time))
        try:
            await _release_concurrency_slots(
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

        _emit_concurrency_release_events(limits, occupy, emitted_events)


async def rate_limit(
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

    limits = await _acquire_concurrency_slots(
        names,
        occupy,
        mode="rate_limit",
        timeout_seconds=timeout_seconds,
        create_if_missing=create_if_missing,
        strict=strict,
    )
    _emit_concurrency_acquisition_events(limits, occupy)


@sync_compatible
@deprecated_parameter(
    name="create_if_missing",
    start_date="Sep 2024",
    end_date="Oct 2024",
    when=lambda x: x is not None,
    help="Limits must be explicitly created before acquiring concurrency slots; see `strict` if you want to enforce this behavior.",
)
async def _acquire_concurrency_slots(
    names: List[str],
    slots: int,
    mode: Union[Literal["concurrency"], Literal["rate_limit"]] = "concurrency",
    timeout_seconds: Optional[float] = None,
    create_if_missing: Optional[bool] = None,
    max_retries: Optional[int] = None,
    strict: bool = False,
) -> List[MinimalConcurrencyLimitResponse]:
    service = ConcurrencySlotAcquisitionService.instance(frozenset(names))
    future = service.send(
        (slots, mode, timeout_seconds, create_if_missing, max_retries)
    )
    response_or_exception = await asyncio.wrap_future(future)

    if isinstance(response_or_exception, Exception):
        if isinstance(response_or_exception, TimeoutError):
            raise AcquireConcurrencySlotTimeoutError(
                f"Attempt to acquire concurrency slots timed out after {timeout_seconds} second(s)"
            ) from response_or_exception

        raise ConcurrencySlotAcquisitionError(
            f"Unable to acquire concurrency slots on {names!r}"
        ) from response_or_exception

    retval = _response_to_minimal_concurrency_limit_response(response_or_exception)

    if strict and not retval:
        raise ConcurrencySlotAcquisitionError(
            f"Concurrency limits {names!r} must be created before acquiring slots"
        )
    elif not retval:
        try:
            logger = get_run_logger()
            logger.warning(
                f"Concurrency limits {names!r} do not exist - skipping acquisition."
            )
        except Exception:
            pass
    return retval


@sync_compatible
async def _release_concurrency_slots(
    names: List[str], slots: int, occupancy_seconds: float
) -> List[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        response = await client.release_concurrency_slots(
            names=names, slots=slots, occupancy_seconds=occupancy_seconds
        )
        return _response_to_minimal_concurrency_limit_response(response)


def _response_to_minimal_concurrency_limit_response(
    response: httpx.Response,
) -> List[MinimalConcurrencyLimitResponse]:
    return [
        MinimalConcurrencyLimitResponse.model_validate(obj_) for obj_ in response.json()
    ]
