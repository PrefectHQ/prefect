import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from docket import Docket, Worker

from prefect.server.api.flow_runs import delete_flow_run_logs
from prefect.server.api.task_runs import delete_task_run_logs
from prefect.server.models.deployments import mark_deployments_ready
from prefect.server.models.work_queues import mark_work_queues_ready
from prefect.settings.context import get_current_settings


@asynccontextmanager
async def background_worker() -> AsyncGenerator[None, None]:
    worker_task: asyncio.Task[None] | None = None
    settings = get_current_settings()
    try:
        async with Docket(
            name="prefect-server", url=settings.server.docket.url
        ) as docket:
            docket.register(mark_work_queues_ready)
            docket.register(mark_deployments_ready)
            docket.register(delete_task_run_logs)
            docket.register(delete_flow_run_logs)

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
