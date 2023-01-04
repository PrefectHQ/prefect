import asyncio
from pathlib import Path

import pytest

from prefect.client.orion import OrionClient
from prefect.exceptions import ObjectNotFound
from prefect.experimental.workers.base import BaseWorker
from prefect.orion.schemas.actions import WorkerPoolQueueCreate
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_WORKER_HEARTBEAT_SECONDS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_QUERY_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_PATH,
    PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS,
)


class WorkerTestImpl(BaseWorker):
    type = "test"

    def run(self):
        pass

    def verify_submitted_deployment(self):
        pass


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS


async def test_worker_raises_if_started_outside_of_context_manager():
    with pytest.raises(RuntimeError, match="Worker has not been setup."):
        await WorkerTestImpl(name="test", worker_pool_name="test-worker-pool").start()


async def test_worker_creates_workflows_directory_during_setup(tmp_path: Path):
    await WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
        workflow_storage_path=tmp_path / "workflows",
    ).setup()
    assert (tmp_path / "workflows").exists()


async def test_worker_creates_worker_pool_by_default_when_started(
    orion_client: OrionClient,
):
    with pytest.raises(ObjectNotFound):
        await orion_client.read_worker_pool("test-worker-pool")

    async with WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
    ) as worker:
        await worker.start()
        worker_status = worker.get_status()
        assert worker_status["worker_pool"]["name"] == "test-worker-pool"

        worker_pool = await orion_client.read_worker_pool("test-worker-pool")
        assert str(worker_pool.id) == worker_status["worker_pool"]["id"]


async def test_worker_does_not_creates_worker_pool_when_create_pool_is_false(
    orion_client: OrionClient,
):
    with pytest.raises(ObjectNotFound):
        await orion_client.read_worker_pool("test-worker-pool")

    async with WorkerTestImpl(
        name="test", worker_pool_name="test-worker-pool", create_pool_if_not_found=False
    ) as worker:
        await worker.start()
        worker_status = worker.get_status()
        assert worker_status["worker_pool"] is None

    with pytest.raises(ObjectNotFound):
        await orion_client.read_worker_pool("test-worker-pool")


@pytest.mark.parametrize(
    "setting,attr",
    [
        (PREFECT_WORKER_QUERY_SECONDS, "query_seconds"),
        (PREFECT_WORKER_HEARTBEAT_SECONDS, "heartbeat_seconds"),
        (PREFECT_WORKER_PREFETCH_SECONDS, "prefetch_seconds"),
        (
            PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS,
            "workflow_storage_scan_seconds",
        ),
        (PREFECT_WORKER_WORKFLOW_STORAGE_PATH, "workflow_storage_path"),
    ],
)
async def test_worker_respects_settings(setting, attr):
    assert (
        WorkerTestImpl(name="test", worker_pool_name="test-worker-pool").get_status()[
            "settings"
        ][attr]
        == setting.value()
    )


async def test_worker_picks_up_new_queues_from_worker_pool(orion_client: OrionClient):
    async with WorkerTestImpl(
        name="test", worker_pool_name="test-worker-pool", heartbeat_seconds=0.1
    ) as worker:
        await worker.start()
        worker_status = worker.get_status()
        assert len(worker_status["worker_pool_queues"]) == 1
        assert worker_status["worker_pool_queues"][0]["name"] == "Default Queue"

        new_queue = await orion_client.create_worker_pool_queue(
            worker_pool_name="test-worker-pool",
            worker_pool_queue=WorkerPoolQueueCreate(name="Custom Queue"),
        )

        # Wait for heartbeat loop
        await asyncio.sleep(0.1)

        worker_status = worker.get_status()
        assert len(worker_status["worker_pool_queues"]) == 2
        assert [
            wpq["name"]
            for wpq in sorted(
                worker_status["worker_pool_queues"], key=lambda wpq: wpq["name"]
            )
        ] == [
            new_queue.name,
            "Default Queue",
        ]


async def test_worker_sends_heartbeat_messages_at_configured_interval(
    orion_client: OrionClient,
):
    async with WorkerTestImpl(
        name="test", worker_pool_name="test-worker-pool", heartbeat_seconds=0.1
    ) as worker:
        await worker.start()

        workers = await orion_client.read_workers_for_worker_pool(
            worker_pool_name="test-worker-pool"
        )
        assert len(workers) == 1
        first_heartbeat = workers[0].last_heartbeat_time
        assert first_heartbeat is not None

        # Wait for heartbeat loop
        await asyncio.sleep(0.1)

        workers = await orion_client.read_workers_for_worker_pool(
            worker_pool_name="test-worker-pool"
        )
        second_heartbeat = workers[0].last_heartbeat_time
        assert second_heartbeat > first_heartbeat
