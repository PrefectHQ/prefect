import asyncio
import logging
from typing import Literal, Optional
from uuid import UUID

import httpx

from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import (
    ConcurrencyLimitWithLeaseResponse,
    MinimalConcurrencyLimitResponse,
)
from prefect.logging import get_logger
from prefect.logging.loggers import get_run_logger
from prefect.utilities.timeout import timeout_async

from .services import ConcurrencySlotAcquisitionService


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
                                logger.warning(
                                    f"Concurrency limits {names!r} do not exist - skipping acquisition."
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
