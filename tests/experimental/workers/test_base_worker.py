from pathlib import Path

import pendulum
import pytest

from prefect.client.orion import OrionClient
from prefect.deployments import Deployment
from prefect.exceptions import ObjectNotFound
from prefect.experimental.workers.base import BaseWorker
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_PATH,
)


class WorkerTestImpl(BaseWorker):
    type = "test"

    async def run(self):
        pass

    async def verify_submitted_deployment(self, deployment):
        pass


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS


async def test_worker_creates_workflows_directory_during_setup(tmp_path: Path):
    await WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
        workflow_storage_path=tmp_path / "workflows",
    ).setup()
    assert (tmp_path / "workflows").exists()


async def test_worker_creates_worker_pool_by_default_during_sync(
    orion_client: OrionClient,
):
    with pytest.raises(ObjectNotFound):
        await orion_client.read_worker_pool("test-worker-pool")

    async with WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
    ) as worker:
        await worker.sync_with_backend()
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
        await worker.sync_with_backend()
        worker_status = worker.get_status()
        assert worker_status["worker_pool"] is None

    with pytest.raises(ObjectNotFound):
        await orion_client.read_worker_pool("test-worker-pool")


@pytest.mark.parametrize(
    "setting,attr",
    [
        (PREFECT_WORKER_PREFETCH_SECONDS, "prefetch_seconds"),
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


async def test_worker_sends_heartbeat_messages(
    orion_client: OrionClient,
):
    async with WorkerTestImpl(
        name="test", worker_pool_name="test-worker-pool"
    ) as worker:
        await worker.sync_with_backend()

        workers = await orion_client.read_workers_for_worker_pool(
            worker_pool_name="test-worker-pool"
        )
        assert len(workers) == 1
        first_heartbeat = workers[0].last_heartbeat_time
        assert first_heartbeat is not None

        await worker.sync_with_backend()

        workers = await orion_client.read_workers_for_worker_pool(
            worker_pool_name="test-worker-pool"
        )
        second_heartbeat = workers[0].last_heartbeat_time
        assert second_heartbeat > first_heartbeat


async def test_worker_applies_discovered_deployments(
    orion_client: OrionClient, flow_function, tmp_path: Path
):
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    deployment = await Deployment.build_from_flow(
        name="test-deployment", flow=flow_function
    )
    await deployment.to_yaml(workflows_path / "test-deployment.yaml")
    async with WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

    read_deployment = await orion_client.read_deployment_by_name(
        "client-test-flow/test-deployment"
    )
    assert read_deployment is not None


async def test_worker_applies_updates_to_deployments(
    orion_client: OrionClient, flow_function, tmp_path: Path
):
    # create initial deployment manifest
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    deployment = await Deployment.build_from_flow(
        name="test-deployment", flow=flow_function
    )
    await deployment.to_yaml(workflows_path / "test-deployment.yaml")
    async with WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None

        # update deployment
        deployment.tags = ["new-tag"]
        deployment.timestamp = pendulum.now("UTC")
        await deployment.to_yaml(workflows_path / "test-deployment.yaml")

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None
        assert read_deployment.tags == ["new-tag"]


async def test_worker_does_not_apply_deployment_updates_for_old_timestamps(
    orion_client: OrionClient, flow_function, tmp_path: Path
):
    # create initial deployment manifest
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    deployment = await Deployment.build_from_flow(
        name="test-deployment", flow=flow_function
    )
    await deployment.to_yaml(workflows_path / "test-deployment.yaml")
    async with WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None

        # update deployment don't update timestamp
        deployment.tags = ["new-tag"]
        await deployment.to_yaml(workflows_path / "test-deployment.yaml")

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None
        assert read_deployment.tags == []


async def test_worker_does_not_raise_on_malformed_manifests(
    orion_client: OrionClient, tmp_path: Path
):
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    (workflows_path / "test-deployment.yaml").write_text(
        "Ceci n'est pas un déploiement"
    )

    async with WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

        assert len(await orion_client.read_deployments()) == 0
