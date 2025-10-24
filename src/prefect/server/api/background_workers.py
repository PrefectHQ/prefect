import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from docket import Docket, Worker

from prefect.server.models.deployments import mark_deployments_ready
from prefect.server.models.work_queues import mark_work_queues_ready


@asynccontextmanager
async def background_worker() -> AsyncGenerator[None, None]:
    worker_task: asyncio.Task[None] | None = None
    try:
        async with Docket(name="prefect-server") as docket:
            docket.register(mark_work_queues_ready)
            docket.register(mark_deployments_ready)

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
