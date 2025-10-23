from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator, Literal, Optional
from uuid import UUID

import anyio
import httpx

from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import (
    ConcurrencyLimitWithLeaseResponse,
    MinimalConcurrencyLimitResponse,
)
from prefect.concurrency._events import (
    emit_concurrency_acquisition_events,
    emit_concurrency_release_events,
)
from prefect.concurrency._leases import amaintain_concurrency_lease
from prefect.concurrency.context import ConcurrencyContext
from prefect.logging import get_logger
from prefect.logging.loggers import get_run_logger
from prefect.utilities.timeout import timeout_async

from .services import ConcurrencySlotAcquisitionService

if TYPE_CHECKING:
    from prefect.client.schemas.objects import ConcurrencyLeaseHolder


class ConcurrencySlotAcquisitionError(Exception):
    """Raised when an unhandlable occurs while acquiring concurrency slots."""


class AcquireConcurrencySlotTimeoutError(TimeoutError):
    """Raised when acquiring a concurrency slot times out."""


logger: logging.Logger = get_logger("concurrency")


async def aacquire_concurrency_slots(
    names: list[str],
    slots: int,
    mode: Literal["concurrency", "rate_limit"] = "concurrency",
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    strict: bool = False,
) -> list[MinimalConcurrencyLimitResponse]:
    service = ConcurrencySlotAcquisitionService.instance(frozenset(names))
    future = service.send((slots, mode, timeout_seconds, max_retries))
    try:
        response = await asyncio.wrap_future(future)
    except TimeoutError as timeout:
        raise AcquireConcurrencySlotTimeoutError(
            f"Attempt to acquire concurrency slots timed out after {timeout_seconds} second(s)"
        ) from timeout
    except Exception as exc:
        raise ConcurrencySlotAcquisitionError(
            f"Unable to acquire concurrency slots on {names!r}"
        ) from exc

    retval = _response_to_minimal_concurrency_limit_response(response)

    if not retval:
        if strict:
            raise ConcurrencySlotAcquisitionError(
                f"Concurrency limits {names!r} must be created before acquiring slots"
            )
        try:
            logger = get_run_logger()
        except Exception:
            pass
        else:
            logger.warning(
                f"Concurrency limits {names!r} do not exist - skipping acquisition."
            )

    return retval


async def aacquire_concurrency_slots_with_lease(
    names: list[str],
    slots: int,
    mode: Literal["concurrency", "rate_limit"] = "concurrency",
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    lease_duration: float = 300,
    strict: bool = False,
    holder: "Optional[ConcurrencyLeaseHolder]" = None,
    suppress_warnings: bool = False,
) -> ConcurrencyLimitWithLeaseResponse:
    try:
        # Use a run logger if available
        logger = get_run_logger()
    except Exception:
        logger = get_logger("concurrency")

    try:
        with timeout_async(seconds=timeout_seconds):
            async with get_client() as client:
                while True:
                    try:
                        response = await client.increment_concurrency_slots_with_lease(
                            names=names,
                            slots=slots,
                            mode=mode,
                            lease_duration=lease_duration,
                            holder=holder,
                        )
                        retval = ConcurrencyLimitWithLeaseResponse.model_validate(
                            response.json()
                        )
                        if not retval.limits:
                            if strict:
                                raise ConcurrencySlotAcquisitionError(
                                    f"Concurrency limits {names!r} must be created before acquiring slots"
                                )
                            else:
                                log_level = (
                                    logging.DEBUG
                                    if suppress_warnings
                                    else logging.WARNING
                                )
                                logger.log(
                                    log_level,
                                    f"Concurrency limits {names!r} do not exist - skipping acquisition.",
                                )

                        return retval
                    except httpx.HTTPStatusError as exc:
                        if not exc.response.status_code == 423:  # HTTP_423_LOCKED
                            raise

                        if max_retries is not None and max_retries <= 0:
                            raise exc
                        retry_after = float(exc.response.headers["Retry-After"])
                        logger.debug(
                            f"Unable to acquire concurrency slot. Retrying in {retry_after} second(s)."
                        )
                        await asyncio.sleep(retry_after)
                        if max_retries is not None:
                            max_retries -= 1
    except TimeoutError as timeout:
        raise AcquireConcurrencySlotTimeoutError(
            f"Attempt to acquire concurrency slots timed out after {timeout_seconds} second(s)"
        ) from timeout
    except Exception as exc:
        raise ConcurrencySlotAcquisitionError(
            f"Unable to acquire concurrency slots on {names!r}"
        ) from exc


async def arelease_concurrency_slots(
    names: list[str], slots: int, occupancy_seconds: float
) -> list[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        response = await client.release_concurrency_slots(
            names=names, slots=slots, occupancy_seconds=occupancy_seconds
        )
        return _response_to_minimal_concurrency_limit_response(response)


async def arelease_concurrency_slots_with_lease(
    lease_id: UUID,
) -> None:
    async with get_client() as client:
        await client.release_concurrency_slots_with_lease(lease_id=lease_id)


def _response_to_minimal_concurrency_limit_response(
    response: httpx.Response,
) -> list[MinimalConcurrencyLimitResponse]:
    return [
        MinimalConcurrencyLimitResponse.model_validate(obj_) for obj_ in response.json()
    ]


@asynccontextmanager
async def concurrency(
    names: str | list[str],
    occupy: int = 1,
    timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    lease_duration: float = 300,
    strict: bool = False,
    holder: "Optional[ConcurrencyLeaseHolder]" = None,
    suppress_warnings: bool = False,
) -> AsyncGenerator[None, None]:
    """
    Internal version of the `concurrency` context manager. The public version is located in `prefect.concurrency.asyncio`.

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
    if not names:
        yield
        return

    names = names if isinstance(names, list) else [names]

    response = await aacquire_concurrency_slots_with_lease(
        names=names,
        slots=occupy,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        lease_duration=lease_duration,
        strict=strict,
        holder=holder,
        suppress_warnings=suppress_warnings,
    )
    emitted_events = emit_concurrency_acquisition_events(response.limits, occupy)

    try:
        async with amaintain_concurrency_lease(
            response.lease_id,
            lease_duration,
            raise_on_lease_renewal_failure=strict,
            suppress_warnings=suppress_warnings,
        ):
            yield
    finally:
        try:
            await arelease_concurrency_slots_with_lease(
                lease_id=response.lease_id,
            )
        except anyio.get_cancelled_exc_class():
            # The task was cancelled before it could release the lease. Add the
            # lease ID to the cleanup list so it can be released when the
            # concurrency context is exited.
            if ctx := ConcurrencyContext.get():
                ctx.cleanup_lease_ids.append(response.lease_id)

        emit_concurrency_release_events(response.limits, occupy, emitted_events)
