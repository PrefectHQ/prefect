import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pendulum
import pytest

from prefect.client.orion import OrionClient
from prefect.deployments import Deployment
from prefect.exceptions import ObjectNotFound
from prefect.experimental.workers.base import BaseWorker
from prefect.flows import flow
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_PATH,
)
from prefect.states import Completed, Pending, Running, Scheduled


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
        name="test-deployment", flow=flow_function, worker_pool_name="test-worker-pool"
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


async def test_worker_with_worker_pool_queue(
    orion_client: OrionClient, deployment, worker_pool
):
    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
        )
    )
    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await orion_client.create_flow_run(test_flow, state=Scheduled()),
    ]
    flow_run_ids = [run.id for run in flow_runs]

    async with WorkerTestImpl(worker_pool_name=worker_pool.name) as worker:
        submitted_flow_runs = await worker.get_and_submit_flow_runs()

    # Should only include scheduled runs in the past or next prefetch seconds
    # Should not include runs without deployments
    assert {flow_run.id for flow_run in submitted_flow_runs} == set(flow_run_ids[1:4])


async def test_worker_with_worker_pool_queue_and_limit(
    orion_client: OrionClient, deployment, worker_pool
):
    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
        )
    )
    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await orion_client.create_flow_run(test_flow, state=Scheduled()),
    ]
    flow_run_ids = [run.id for run in flow_runs]

    async with WorkerTestImpl(worker_pool_name=worker_pool.name, limit=2) as worker:
        worker._submit_run = AsyncMock()  # don't run anything

        submitted_flow_runs = await worker.get_and_submit_flow_runs()
        assert {flow_run.id for flow_run in submitted_flow_runs} == set(
            flow_run_ids[1:3]
        )

        submitted_flow_runs = await worker.get_and_submit_flow_runs()
        assert {flow_run.id for flow_run in submitted_flow_runs} == set(
            flow_run_ids[1:3]
        )

        worker._limiter.release_on_behalf_of(flow_run_ids[1])

        submitted_flow_runs = await worker.get_and_submit_flow_runs()
        assert {flow_run.id for flow_run in submitted_flow_runs} == set(
            flow_run_ids[1:4]
        )


async def test_worker_calls_run_with_expected_arguments(
    orion_client: OrionClient, deployment, worker_pool
):
    run_mock = AsyncMock()

    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
        )
    )
    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await orion_client.create_flow_run(test_flow, state=Scheduled()),
    ]

    async with WorkerTestImpl(worker_pool_name=worker_pool.name) as worker:
        worker.run = run_mock  # don't run anything
        await worker.get_and_submit_flow_runs()
        await asyncio.sleep(1)

    assert run_mock.call_count == 3
    assert {call.kwargs["flow_run"].id for call in run_mock.call_args_list} == {
        fr.id for fr in flow_runs[1:4]
    }
