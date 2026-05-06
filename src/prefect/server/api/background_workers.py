import asyncio
import random
from contextlib import asynccontextmanager
from logging import Logger
from typing import Any, AsyncGenerator, Callable

from docket import Docket, Worker

from prefect.logging import get_logger
from prefect.server.api.flow_runs import delete_flow_run_logs
from prefect.server.api.task_runs import delete_task_run_logs
from prefect.server.events.services import triggers as _triggers_module  # noqa: F401
from prefect.server.models.deployments import mark_deployments_ready
from prefect.server.models.work_queues import mark_work_queues_ready
from prefect.server.services.cancellation_cleanup import (
    cancel_child_task_runs,
    cancel_subflow_run,
)
from prefect.server.services.late_runs import mark_flow_run_late
from prefect.server.services.pause_expirations import fail_expired_pause
from prefect.server.services.perpetual_services import (
    register_and_schedule_perpetual_services,
)
from prefect.server.services.repossessor import revoke_expired_lease
from prefect.settings.context import get_current_settings

logger: Logger = get_logger(__name__)

# Task functions to register with docket for background processing
task_functions: list[Callable[..., Any]] = [
    # Simple background tasks (from Alex's PR #19377)
    mark_work_queues_ready,
    mark_deployments_ready,
    delete_task_run_logs,
    delete_flow_run_logs,
    # Find-and-flood pattern tasks used by perpetual services
    cancel_child_task_runs,
    cancel_subflow_run,
    fail_expired_pause,
    mark_flow_run_late,
    revoke_expired_lease,
]


async def _run_worker_with_reconnect(
    docket_factory: Callable[[], Docket],
    ephemeral: bool,
    webserver_only: bool,
    shutdown_event: asyncio.Event,
) -> None:
    """
    Supervise a docket Worker, rebuilding both the Worker and the Docket on
    any unexpected failure.

    Rebuilding the Docket on each attempt drops the old Redis connection pool
    and re-resolves the URL. Without this, a Redis failover leaves the pool
    pinned to the now-read-only replica and every rebuilt Worker keeps hitting
    `ReadOnlyError` on the perpetual-task lock.
    """
    settings = get_current_settings().server.docket
    base_delay = settings.worker_reconnect_base_delay_seconds
    max_delay = settings.worker_reconnect_max_delay_seconds
    max_attempts = settings.worker_max_restart_attempts

    consecutive_failures = 0

    while not shutdown_event.is_set():
        try:
            async with docket_factory() as docket:
                async with Worker(docket) as worker:
                    docket.register_collection(
                        "prefect.server.api.background_workers:task_functions"
                    )
                    await register_and_schedule_perpetual_services(
                        docket,
                        ephemeral=ephemeral,
                        webserver_only=webserver_only,
                    )
                    await worker.run_forever()
                    # Returned cleanly despite `forever=True`. Treat as a failure
                    # so we rebuild rather than exit the supervisor silently.
                    raise RuntimeError(
                        "docket Worker.run_forever returned unexpectedly"
                    )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            consecutive_failures += 1
            if max_attempts and consecutive_failures > max_attempts:
                logger.exception(
                    "docket worker failed %d times; giving up",
                    consecutive_failures,
                )
                raise

            delay = min(max_delay, base_delay * (2 ** (consecutive_failures - 1)))
            delay *= 0.5 + random.random()  # jitter in [0.5*delay, 1.5*delay]
            delay = min(delay, max_delay)

            logger.error(
                "docket worker failed (attempt %d): %s: %s. "
                "Rebuilding Docket and restarting in %.1fs.",
                consecutive_failures,
                type(exc).__name__,
                exc,
                delay,
                exc_info=True,
            )

            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
                return  # shutdown signalled during backoff
            except asyncio.TimeoutError:
                continue


@asynccontextmanager
async def background_worker(
    docket_factory: Callable[[], Docket],
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> AsyncGenerator[None, None]:
    shutdown_event = asyncio.Event()
    supervisor_task: asyncio.Task[None] = asyncio.create_task(
        _run_worker_with_reconnect(
            docket_factory,
            ephemeral=ephemeral,
            webserver_only=webserver_only,
            shutdown_event=shutdown_event,
        ),
        name="docket-worker-supervisor",
    )

    try:
        yield
    finally:
        shutdown_event.set()
        supervisor_task.cancel()
        try:
            await supervisor_task
        except asyncio.CancelledError:
            pass
