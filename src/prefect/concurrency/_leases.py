import asyncio
import concurrent.futures
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Callable, Generator
from uuid import UUID

import httpx

from prefect._internal.concurrency.api import create_call
from prefect._internal.concurrency.cancellation import (
    AsyncCancelScope,
    WatcherThreadCancelScope,
)
from prefect._internal.concurrency.threads import get_global_loop
from prefect._internal.retries import retry_async_fn
from prefect.client.orchestration import get_client
from prefect.logging.loggers import get_logger, get_run_logger


async def _lease_renewal_loop(
    lease_id: UUID,
    lease_duration: float,
    should_stop: Callable[[], bool] = lambda: False,
) -> None:
    """
    Maintain a concurrency lease by renewing it after the given interval.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        should_stop: An optional callable that returns True when the renewal loop
            should exit cleanly. Checked before each renewal attempt so that the
            loop can stop without raising when the flow has already reached a
            terminal state (e.g. the server will release the lease itself).
    """
    async with get_client() as client:

        @retry_async_fn(
            max_attempts=3,
            operation_name="concurrency lease renewal",
            should_not_retry=lambda e: (
                isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 410
            ),
        )
        async def renew() -> None:
            await client.renew_concurrency_lease(
                lease_id=lease_id, lease_duration=lease_duration
            )

        while True:
            # Exit cleanly if the caller signals that the flow is done.
            if should_stop():
                return
            await renew()
            await asyncio.sleep(  # Renew the lease 3/4 of the way through the lease duration
                lease_duration * 0.75
            )


@contextmanager
def maintain_concurrency_lease(
    lease_id: UUID,
    lease_duration: float,
    raise_on_lease_renewal_failure: bool = False,
    suppress_warnings: bool = False,
    should_stop: Callable[[], bool] = lambda: False,
) -> Generator[None, None, None]:
    """
    Maintain a concurrency lease for the given lease ID.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise an error if the lease renewal fails.
        should_stop: An optional callable that returns True when the renewal loop
            should exit cleanly without treating a failure as a crash. Typically
            set to a check on the engine's current flow run state so that renewal
            failures that occur after a successful terminal state transition are
            silently ignored instead of propagated as crashes.
    """
    # Start a loop to renew the lease on the global event loop to avoid blocking the main thread
    global_loop = get_global_loop()
    lease_renewal_call = create_call(
        _lease_renewal_loop,
        lease_id,
        lease_duration,
        should_stop,
    )
    global_loop.submit(lease_renewal_call)

    with WatcherThreadCancelScope() as cancel_scope:

        def handle_lease_renewal_failure(future: concurrent.futures.Future[None]):
            if future.cancelled():
                return
            exc = future.exception()
            if exc:
                try:
                    logger = get_run_logger()
                except Exception:
                    logger = get_logger("concurrency")

                if should_stop():
                    logger.debug(
                        "Concurrency lease renewal failed after flow reached terminal state - this is expected.",
                        exc_info=(type(exc), exc, exc.__traceback__),
                    )
                    return

                if raise_on_lease_renewal_failure:
                    logger.error(
                        "Concurrency lease renewal failed - slots are no longer reserved. Terminating execution to prevent over-allocation.",
                        exc_info=(type(exc), exc, exc.__traceback__),
                    )
                    assert cancel_scope.cancel()
                else:
                    if suppress_warnings:
                        logger.debug(
                            "Concurrency lease renewal failed - slots are no longer reserved. Execution will continue, but concurrency limits may be exceeded.",
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )
                    else:
                        logger.warning(
                            "Concurrency lease renewal failed - slots are no longer reserved. Execution will continue, but concurrency limits may be exceeded.",
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )

        lease_renewal_call.future.add_done_callback(handle_lease_renewal_failure)

        try:
            yield
        finally:
            # Cancel the lease renewal loop
            lease_renewal_call.cancel()


@asynccontextmanager
async def amaintain_concurrency_lease(
    lease_id: UUID,
    lease_duration: float,
    raise_on_lease_renewal_failure: bool = False,
    suppress_warnings: bool = False,
    should_stop: Callable[[], bool] = lambda: False,
) -> AsyncGenerator[None, None]:
    """
    Maintain a concurrency lease for the given lease ID.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise an error if the lease renewal fails.
        should_stop: An optional callable that returns True when the renewal loop
            should exit cleanly without treating a failure as a crash. Typically
            set to a check on the engine's current flow run state so that renewal
            failures that occur after a successful terminal state transition are
            silently ignored instead of propagated as crashes.
    """
    lease_renewal_task = asyncio.create_task(
        _lease_renewal_loop(lease_id, lease_duration, should_stop)
    )
    with AsyncCancelScope() as cancel_scope:

        def handle_lease_renewal_failure(task: asyncio.Task[None]):
            if task.cancelled():
                # Cancellation is the expected way for this loop to stop
                return
            exc = task.exception()
            if exc:
                try:
                    logger = get_run_logger()
                except Exception:
                    logger = get_logger("concurrency")

                if should_stop():
                    logger.debug(
                        "Concurrency lease renewal failed after flow reached terminal state - this is expected.",
                        exc_info=(type(exc), exc, exc.__traceback__),
                    )
                    return

                if raise_on_lease_renewal_failure:
                    logger.error(
                        "Concurrency lease renewal failed - slots are no longer reserved. Terminating execution to prevent over-allocation.",
                        exc_info=(type(exc), exc, exc.__traceback__),
                    )
                    cancel_scope.cancel()
                else:
                    if suppress_warnings:
                        logger.debug(
                            "Concurrency lease renewal failed - slots are no longer reserved. Execution will continue, but concurrency limits may be exceeded.",
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )
                    else:
                        logger.warning(
                            "Concurrency lease renewal failed - slots are no longer reserved. Execution will continue, but concurrency limits may be exceeded.",
                            exc_info=(type(exc), exc, exc.__traceback__),
                        )

        # Add a callback to stop execution if the lease renewal fails and strict is True
        lease_renewal_task.add_done_callback(handle_lease_renewal_failure)
        try:
            yield
        finally:
            lease_renewal_task.cancel()
            try:
                await lease_renewal_task
            except (asyncio.CancelledError, Exception, BaseException):
                # Handling for errors will be done in the callback
                pass
