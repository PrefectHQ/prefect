import asyncio
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


@asynccontextmanager
async def background_worker(
    docket: Docket,
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> AsyncGenerator[None, None]:
    worker_task: asyncio.Task[None] | None = None
    async with Worker(docket) as worker:
        # Register background task functions
        docket.register_collection(
            "prefect.server.api.background_workers:task_functions"
        )

        # Register and schedule enabled perpetual services
        await register_and_schedule_perpetual_services(
            docket, ephemeral=ephemeral, webserver_only=webserver_only
        )

        try:
            worker_task = asyncio.create_task(worker.run_forever())
            yield

        finally:
            if worker_task:
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass
