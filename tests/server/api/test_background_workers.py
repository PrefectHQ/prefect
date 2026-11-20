import asyncio
from uuid import uuid4

from docket import Docket, Worker

from prefect.server.api.background_workers import background_worker


async def test_background_worker_shuts_down_when_worker_cancellation_is_lost(
    monkeypatch,
):
    """
    On Python 3.11, `asyncio.wait_for` can swallow a cancellation when its inner
    future completes in the same loop iteration. docket's worker uses `wait_for`
    internally, so `worker_task.cancel()` alone may not stop it and shutdown
    would hang. Simulate that lost cancellation and ensure shutdown still
    completes.
    """
    original_run_forever = Worker.run_forever
    worker_started = asyncio.Event()
    cancellation_ignored = asyncio.Event()

    async def run_forever_ignoring_cancellation(self: Worker) -> None:
        async def run() -> None:
            worker_started.set()
            await original_run_forever(self)

        inner = asyncio.ensure_future(run())
        while True:
            try:
                return await asyncio.shield(inner)
            except asyncio.CancelledError:
                cancellation_ignored.set()

    monkeypatch.setattr(Worker, "run_forever", run_forever_ignoring_cancellation)

    docket = Docket(name=f"test-docket-{uuid4().hex[:8]}", url="memory://")
    async with docket, background_worker(docket, ephemeral=True):
        await worker_started.wait()

    assert cancellation_ignored.is_set()
