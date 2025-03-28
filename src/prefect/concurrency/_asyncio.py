import asyncio
from typing import Literal, Optional

import httpx

from prefect.client.orchestration import get_client
from prefect.client.schemas.responses import MinimalConcurrencyLimitResponse
from prefect.logging.loggers import get_run_logger

from .services import ConcurrencySlotAcquisitionService


class ConcurrencySlotAcquisitionError(Exception):
    """Raised when an unhandlable occurs while acquiring concurrency slots."""


class AcquireConcurrencySlotTimeoutError(TimeoutError):
    """Raised when acquiring a concurrency slot times out."""


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


async def arelease_concurrency_slots(
    names: list[str], slots: int, occupancy_seconds: float
) -> list[MinimalConcurrencyLimitResponse]:
    async with get_client() as client:
        response = await client.release_concurrency_slots(
            names=names, slots=slots, occupancy_seconds=occupancy_seconds
        )
        return _response_to_minimal_concurrency_limit_response(response)


def _response_to_minimal_concurrency_limit_response(
    response: httpx.Response,
) -> list[MinimalConcurrencyLimitResponse]:
    return [
        MinimalConcurrencyLimitResponse.model_validate(obj_) for obj_ in response.json()
    ]
