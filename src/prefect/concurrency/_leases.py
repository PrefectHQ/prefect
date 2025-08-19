import asyncio
import concurrent.futures
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator
from uuid import UUID

from prefect._internal.concurrency.api import create_call
from prefect._internal.concurrency.cancellation import (
    AsyncCancelScope,
    WatcherThreadCancelScope,
)
from prefect._internal.concurrency.threads import get_global_loop
from prefect.client.orchestration import get_client
from prefect.logging.loggers import get_logger, get_run_logger


async def _lease_renewal_loop(
    lease_id: UUID,
    lease_duration: float,
) -> None:
    """
    Maintain a concurrency lease by renewing it after the given interval.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
    """
    async with get_client() as client:
        while True:
            await client.renew_concurrency_lease(
                lease_id=lease_id, lease_duration=lease_duration
            )
            await asyncio.sleep(  # Renew the lease 3/4 of the way through the lease duration
                lease_duration * 0.75
            )


@contextmanager
def maintain_concurrency_lease(
    lease_id: UUID,
    lease_duration: float,
    raise_on_lease_renewal_failure: bool = False,
) -> Generator[None, None, None]:
    """
    Maintain a concurrency lease for the given lease ID.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise an error if the lease renewal fails.
    """
    # Start a loop to renew the lease on the global event loop to avoid blocking the main thread
    global_loop = get_global_loop()
    lease_renewal_call = create_call(
        _lease_renewal_loop,
        lease_id,
        lease_duration,
    )
    global_loop.submit(lease_renewal_call)

    with WatcherThreadCancelScope() as cancel_scope:

        def handle_lease_renewal_failure(future: concurrent.futures.Future[None]):
            if future.cancelled():
                return
            exc = future.exception()
            if exc:
                try:
                    # Use a run logger if available
                    logger = get_run_logger()
                except Exception:
                    logger = get_logger("concurrency")
                if raise_on_lease_renewal_failure:
                    logger.error(
                        "Concurrency lease renewal failed - slots are no longer reserved. Terminating execution to prevent over-allocation."
                    )
                    assert cancel_scope.cancel()
                else:
                    logger.warning(
                        "Concurrency lease renewal failed - slots are no longer reserved. Execution will continue, but concurrency limits may be exceeded."
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
) -> AsyncGenerator[None, None]:
    """
    Maintain a concurrency lease for the given lease ID.

    Args:
        lease_id: The ID of the lease to maintain.
        lease_duration: The duration of the lease in seconds.
        raise_on_lease_renewal_failure: A boolean specifying whether to raise an error if the lease renewal fails.
    """
    lease_renewal_task = asyncio.create_task(
        _lease_renewal_loop(lease_id, lease_duration)
    )
    with AsyncCancelScope() as cancel_scope:

        def handle_lease_renewal_failure(task: asyncio.Task[None]):
            if task.cancelled():
                # Cancellation is the expected way for this loop to stop
                return
            exc = task.exception()
            if exc:
                try:
                    # Use a run logger if available
                    logger = get_run_logger()
                except Exception:
                    logger = get_logger("concurrency")
                if raise_on_lease_renewal_failure:
                    logger.error(
                        "Concurrency lease renewal failed - slots are no longer reserved. Terminating execution to prevent over-allocation."
                    )
                    cancel_scope.cancel()
                else:
                    logger.warning(
                        "Concurrency lease renewal failed - slots are no longer reserved. Execution will continue, but concurrency limits may be exceeded."
                    )

        # Add a callback to stop execution if the lease renewal fails and strict is True
        lease_renewal_task.add_done_callback(handle_lease_renewal_failure)
        try:
            yield
        finally:
            lease_renewal_task.cancel()
            try:
                await lease_renewal_task
            except (asyncio.CancelledError, Exception):
                # Handling for errors will be done in the callback
                pass
