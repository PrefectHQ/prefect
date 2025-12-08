import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from docket import Docket, Worker

from prefect.server.api.flow_runs import delete_flow_run_logs
from prefect.server.api.task_runs import delete_task_run_logs

# Import triggers module to ensure evaluate_proactive_triggers_perpetual is registered
from prefect.server.events.services import triggers  # noqa: F401
from prefect.server.models.deployments import mark_deployments_ready
from prefect.server.models.work_queues import mark_work_queues_ready

# Import task functions that need to be registered with docket
from prefect.server.services.cancellation_cleanup import (
    cancel_child_task_runs,
    cancel_subflow_run,
)
from prefect.server.services.foreman import (
    mark_deployments_not_ready_task,
    mark_work_pools_not_ready,
    mark_work_queues_not_ready_task,
    mark_workers_offline,
)
from prefect.server.services.late_runs import mark_flow_run_late
from prefect.server.services.pause_expirations import fail_expired_pause
from prefect.server.services.perpetual_services import (
    register_and_schedule_perpetual_services,
)
from prefect.server.services.repossessor import revoke_expired_lease


@asynccontextmanager
async def background_worker(
    docket: Docket,
    ephemeral: bool = False,
    webserver_only: bool = False,
) -> AsyncGenerator[None, None]:
    worker_task: asyncio.Task[None] | None = None
    try:
        # Register simple background task functions
        docket.register(mark_work_queues_ready)
        docket.register(mark_deployments_ready)
        docket.register(delete_task_run_logs)
        docket.register(delete_flow_run_logs)

        # Register task functions used by perpetual services (find-and-flood pattern)
        docket.register(mark_flow_run_late)
        docket.register(fail_expired_pause)
        docket.register(cancel_child_task_runs)
        docket.register(cancel_subflow_run)
        docket.register(revoke_expired_lease)
        docket.register(mark_workers_offline)
        docket.register(mark_work_pools_not_ready)
        docket.register(mark_deployments_not_ready_task)
        docket.register(mark_work_queues_not_ready_task)

        # Register and schedule enabled perpetual services
        await register_and_schedule_perpetual_services(
            docket, ephemeral=ephemeral, webserver_only=webserver_only
        )

        async with Worker(docket) as worker:
            worker_task = asyncio.create_task(worker.run_forever())
            yield

    finally:
        if worker_task:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
