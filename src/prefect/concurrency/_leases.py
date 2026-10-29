import contextvars
import threading
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, AsyncGenerator, Generator
from uuid import UUID

import httpx

from prefect._internal.compatibility.starlette import status
from prefect._internal.concurrency.cancellation import (
    AsyncCancelScope,
    WatcherThreadCancelScope,
)
from prefect._internal.retries import exponential_backoff_with_jitter
from prefect.client.orchestration import get_client
from prefect.logging.loggers import get_logger, get_run_logger

if TYPE_CHECKING:
    from prefect.client.orchestration import SyncPrefectClient

_RENEWAL_FRACTION = 0.75
_RENEWAL_MAX_ATTEMPTS = 3
_RENEWAL_RETRY_BASE_DELAY = 1
_RENEWAL_RETRY_MAX_DELAY = 10


def _renew_concurrency_lease_with_retries(
    client: "SyncPrefectClient",
    lease_id: UUID,
    lease_duration: float,
    stop_event: threading.Event,
) -> bool:
    """
    Renew a concurrency lease, retrying transient failures.

    Returns `False` when shutdown is requested during retry backoff.
    """
    logger = get_logger("concurrency")

    for attempt in range(_RENEWAL_MAX_ATTEMPTS):
        try:
            client.renew_concurrency_lease(
                lease_id=lease_id, lease_duration=lease_duration
            )
            return True
        except Exception as exc:
            if attempt == _RENEWAL_MAX_ATTEMPTS - 1:
                logger.exception(
                    "Function 'concurrency lease renewal' failed after %s attempts",
                    _RENEWAL_MAX_ATTEMPTS,
                )
                raise

            delay = exponential_backoff_with_jitter(
                attempt,
                _RENEWAL_RETRY_BASE_DELAY,
                _RENEWAL_RETRY_MAX_DELAY,
            )
            logger.warning(
                "Attempt %s of function 'concurrency lease renewal' failed with "
                "%s: %s. Retrying in %.2f seconds...",
                attempt + 1,
                type(exc).__name__,
                exc,
                delay,
            )
            if stop_event.wait(delay):
                return False

    return False


def _lease_renewal_loop(
    lease_id: UUID,
    lease_duration: float,
    stop_event: threading.Event,
) -> None:
    """
    Maintain a concurrency lease until stopped.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        stop_event: Event set by the owning context manager on exit.
    """
    with get_client(sync_client=True) as client:
        while not stop_event.is_set():
            renewed = _renew_concurrency_lease_with_retries(
                client, lease_id, lease_duration, stop_event
            )
            if not renewed:
                return
            stop_event.wait(lease_duration * _RENEWAL_FRACTION)


def _lease_released_by_final_flow_run(
    exc: BaseException, lease_id: UUID, flow_run_id: UUID | None
) -> bool:
    """
    Check whether a lease renewal failure is explained by the flow run having
    reached a final state on the server, which releases the lease before the
    engine has received the response to its terminal state proposal.
    """
    if flow_run_id is None or not (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code == status.HTTP_410_GONE
    ):
        return False

    logger = get_logger("concurrency")
    try:
        with get_client(sync_client=True) as client:
            flow_run = client.read_flow_run(flow_run_id)
    except Exception:
        logger.debug(
            "Failed to read flow run %s after its concurrency lease was not found",
            flow_run_id,
            exc_info=True,
        )
        return False

    if flow_run.state is None or not flow_run.state.is_final():
        return False

    logger.debug(
        "Concurrency lease %s was released because flow run %s reached final "
        "state %s; stopping lease renewal",
        lease_id,
        flow_run_id,
        flow_run.state.type.value,
    )
    return True


def _handle_lease_renewal_failure(
    exc: BaseException,
    lease_id: UUID,
    raise_on_lease_renewal_failure: bool,
    suppress_warnings: bool,
    cancel_scope: AsyncCancelScope | WatcherThreadCancelScope,
) -> None:
    try:
        # Use a run logger if available
        logger = get_run_logger()
    except Exception:
        logger = get_logger("concurrency")

    if raise_on_lease_renewal_failure:
        logger.error(
            "Concurrency lease renewal failed - slots are no longer reserved. "
            "Terminating execution to prevent over-allocation. "
            "Lease ID: %s, exception: %s",
            lease_id,
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        cancel_scope.cancel()
    elif suppress_warnings:
        logger.debug(
            "Concurrency lease renewal failed - slots are no longer reserved. "
            "Execution will continue, but concurrency limits may be exceeded. "
            "Lease ID: %s, exception: %s",
            lease_id,
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    else:
        logger.warning(
            "Concurrency lease renewal failed - slots are no longer reserved. "
            "Execution will continue, but concurrency limits may be exceeded. "
            "Lease ID: %s, exception: %s",
            lease_id,
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )


def _start_lease_renewal_thread(
    lease_id: UUID,
    lease_duration: float,
    raise_on_lease_renewal_failure: bool,
    suppress_warnings: bool,
    cancel_scope: AsyncCancelScope | WatcherThreadCancelScope,
    flow_run_id: UUID | None = None,
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    renewal_ctx = contextvars.copy_context()

    def _run_with_failure_handler() -> None:
        # Runs inside renewal_ctx so the failure handler also sees the
        # copied flow/task run contextvars; otherwise get_run_logger() in
        # _handle_lease_renewal_failure can't find the run context and the
        # message falls back to the plain "prefect.concurrency" logger,
        # never reaching the run logs API.
        try:
            _lease_renewal_loop(lease_id, lease_duration, stop_event)
        except Exception as exc:
            if stop_event.is_set() or _lease_released_by_final_flow_run(
                exc, lease_id, flow_run_id
            ):
                return
            _handle_lease_renewal_failure(
                exc,
                lease_id,
                raise_on_lease_renewal_failure,
                suppress_warnings,
                cancel_scope,
            )

    def renewal_loop() -> None:
        renewal_ctx.run(_run_with_failure_handler)

    thread = threading.Thread(
        target=renewal_loop,
        daemon=True,
        name=f"concurrency-lease-renewal-{lease_id}",
    )
    thread.start()
    return stop_event, thread


@contextmanager
def maintain_concurrency_lease(
    lease_id: UUID,
    lease_duration: float,
    raise_on_lease_renewal_failure: bool = False,
    suppress_warnings: bool = False,
    flow_run_id: UUID | None = None,
) -> Generator[None, None, None]:
    """
    Maintain a concurrency lease for the given lease ID.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise an error if the lease renewal fails.
        flow_run_id: The ID of the flow run holding the lease. When the lease is
            not found and this flow run is final on the server, the lease was
            released by the terminal transition and execution is not terminated.
    """
    with WatcherThreadCancelScope() as cancel_scope:
        stop_event: threading.Event | None = None
        thread: threading.Thread | None = None
        try:
            stop_event, thread = _start_lease_renewal_thread(
                lease_id,
                lease_duration,
                raise_on_lease_renewal_failure,
                suppress_warnings,
                cancel_scope,
                flow_run_id,
            )
            yield
        finally:
            if stop_event is not None:
                stop_event.set()
            if thread is not None:
                thread.join(timeout=2)


@asynccontextmanager
async def amaintain_concurrency_lease(
    lease_id: UUID,
    lease_duration: float,
    raise_on_lease_renewal_failure: bool = False,
    suppress_warnings: bool = False,
    flow_run_id: UUID | None = None,
) -> AsyncGenerator[None, None]:
    """
    Maintain a concurrency lease for the given lease ID.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise an error if the lease renewal fails.
        flow_run_id: The ID of the flow run holding the lease. When the lease is
            not found and this flow run is final on the server, the lease was
            released by the terminal transition and execution is not terminated.
    """
    with AsyncCancelScope() as cancel_scope:
        stop_event: threading.Event | None = None
        try:
            stop_event, _ = _start_lease_renewal_thread(
                lease_id,
                lease_duration,
                raise_on_lease_renewal_failure,
                suppress_warnings,
                cancel_scope,
                flow_run_id,
            )
            yield
        finally:
            if stop_event is not None:
                stop_event.set()
