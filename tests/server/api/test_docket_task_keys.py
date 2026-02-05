"""
Tests for docket task keys in API handlers.

These tests verify that API handlers use consistent, deterministic task keys when
scheduling background docket tasks. Task keys ensure at-most-once execution semantics,
preventing duplicate task execution when multiple API servers process the same request.

See: https://github.com/PrefectHQ/prefect/pull/19936#issuecomment-3744457809
"""

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

import httpx
import pytest
from docket import Docket
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.compatibility.starlette import status
from prefect.server import models, schemas
from prefect.server.schemas.statuses import DeploymentStatus
from prefect.settings import get_current_settings


@asynccontextmanager
async def docket_without_worker_lifespan(
    app: FastAPI,
) -> AsyncGenerator[None, None]:
    """
    Custom lifespan context that starts Docket and registers task functions,
    but does NOT start the background worker. This allows tasks to accumulate
    in the queue for proper deduplication testing.

    Uses a unique Docket name per test to avoid Redis key collisions when
    using the shared fakeredis server.
    """
    settings = get_current_settings()
    unique_name = f"test-docket-{uuid4().hex[:8]}"
    async with Docket(
        name=unique_name,
        url=settings.server.docket.url,
        execution_ttl=timedelta(0),
    ) as docket:
        docket.register_collection(
            "prefect.server.api.background_workers:task_functions"
        )
        app.api_app.state.docket = docket
        yield


@pytest.fixture
async def client_with_real_docket(
    app: FastAPI,
) -> AsyncGenerator[AsyncClient, Any]:
    """
    Yield a test client with a real Docket instance but NO background worker.

    This ensures tasks stay in the queue and are not processed, allowing us to
    properly verify that duplicate task keys are deduplicated.

    Note: We intentionally do NOT use LifespanManager(app) here because that
    would trigger the app's lifespan which starts the background worker.
    The database session fixture handles DB setup separately.
    """
    async with docket_without_worker_lifespan(app):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="https://test/api"
        ) as async_client:
            yield async_client


@pytest.fixture
async def real_docket(app: FastAPI, client_with_real_docket: AsyncClient) -> Docket:
    """Get the real Docket instance from the app.

    Depends on client_with_real_docket to ensure lifespan context is active.
    """
    return app.api_app.state.docket


class TestDocketAtMostOnceExecution:
    """
    Integration tests verifying at-most-once execution semantics using real Docket.

    These tests make duplicate API requests and verify that only one task is queued
    in Docket, demonstrating that the task keys prevent duplicate execution.
    """

    @pytest.fixture
    async def work_queue(self, session: AsyncSession):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.actions.WorkQueueCreate(
                name=f"test-wq-{uuid4().hex[:8]}"
            ),
        )
        await session.commit()
        return work_queue

    @pytest.fixture
    async def work_pool(self, session: AsyncSession):
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name=f"test-pool-{uuid4().hex[:8]}",
                type="test",
            ),
        )
        await session.commit()
        return work_pool

    @pytest.fixture
    async def flow(self, session: AsyncSession):
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-{uuid4().hex[:8]}"),
        )
        await session.commit()
        return flow

    @pytest.fixture
    async def deployments(self, session: AsyncSession, flow):
        deployments = []
        for i in range(3):
            deployment = await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name=f"test-deployment-{i}",
                    flow_id=flow.id,
                    status=DeploymentStatus.READY,
                ),
            )
            deployments.append(deployment)
        await session.commit()
        return deployments

    @pytest.fixture
    async def flow_run(self, session: AsyncSession, flow):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return flow_run

    @pytest.fixture
    async def task_run(self, session: AsyncSession, flow_run):
        task_run = await models.task_runs.create_task_run(
            session=session,
            task_run=schemas.core.TaskRun(
                flow_run_id=flow_run.id,
                task_key="test-task",
                dynamic_key="0",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return task_run

    async def test_work_queue_duplicate_requests_queue_single_task(
        self,
        work_queue,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        """
        Verify that duplicate requests to read work queue runs only queue one task
        per unique key, demonstrating at-most-once execution.
        """
        # Get initial snapshot
        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        # Make the same request multiple times
        for _ in range(3):
            response = await client_with_real_docket.post(
                f"/work_queues/{work_queue.id}/get_runs",
            )
            assert response.status_code == status.HTTP_200_OK

        # Get snapshot after requests
        final_snapshot = await real_docket.snapshot()

        # Should only have 2 new tasks (mark_work_queues_ready and mark_deployments_ready)
        # despite making 3 requests, because duplicate keys are ignored
        new_tasks = final_snapshot.total_tasks - initial_task_count
        assert new_tasks == 2, (
            f"Expected 2 tasks (one per unique key), but got {new_tasks}. "
            "Duplicate requests should not create additional tasks."
        )

        # Verify the tasks have the expected keys
        # Include both future (queued) and running tasks since the worker may have
        # already started processing some tasks by the time we take the snapshot
        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        expected_keys = {
            f"mark_work_queues_ready:{work_queue.id}",
            f"mark_deployments_ready:work_queue:{work_queue.id}",
        }
        assert expected_keys.issubset(task_keys), (
            f"Expected keys {expected_keys} not found in {task_keys}"
        )

    async def test_workers_duplicate_requests_queue_single_task(
        self,
        work_pool,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        """
        Verify that duplicate requests to get scheduled flow runs only queue one task
        per unique key.
        """
        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        # Make the same request multiple times
        for _ in range(3):
            response = await client_with_real_docket.post(
                f"/work_pools/{work_pool.name}/get_scheduled_flow_runs",
                json={},
            )
            assert response.status_code == status.HTTP_200_OK

        final_snapshot = await real_docket.snapshot()
        new_tasks = final_snapshot.total_tasks - initial_task_count

        # Should only have 2 new tasks despite 3 requests
        assert new_tasks == 2, (
            f"Expected 2 tasks, but got {new_tasks}. "
            "Duplicate requests should not create additional tasks."
        )

        # Include both future (queued) and running tasks since the worker may have
        # already started processing some tasks by the time we take the snapshot
        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        expected_keys = {
            f"mark_work_queues_ready:work_pool:{work_pool.id}",
            f"mark_deployments_ready:work_pool:{work_pool.id}",
        }
        assert expected_keys.issubset(task_keys)

    async def test_deployments_duplicate_requests_queue_single_task(
        self,
        deployments,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        """
        Verify that duplicate requests for deployment scheduled runs only queue
        one task per unique key.
        """
        deployment_ids = [str(d.id) for d in deployments]

        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        # Make the same request multiple times
        for _ in range(3):
            response = await client_with_real_docket.post(
                "/deployments/get_scheduled_flow_runs",
                json={"deployment_ids": deployment_ids},
            )
            assert response.status_code == status.HTTP_200_OK

        final_snapshot = await real_docket.snapshot()
        new_tasks = final_snapshot.total_tasks - initial_task_count

        # Should only have 1 new task despite 3 requests
        assert new_tasks == 1, (
            f"Expected 1 task, but got {new_tasks}. "
            "Duplicate requests should not create additional tasks."
        )

        sorted_ids = ",".join(str(d) for d in sorted(UUID(id) for id in deployment_ids))
        expected_key = f"mark_deployments_ready:deployments:{sorted_ids}"
        # Include both future (queued) and running tasks since the worker may have
        # already started processing some tasks by the time we take the snapshot
        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        assert expected_key in task_keys

    async def test_deployments_different_order_same_task(
        self,
        deployments,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        """
        Verify that requests with deployment IDs in different orders result in
        the same task key, preventing duplicate execution.
        """
        deployment_ids = [str(d.id) for d in deployments]
        reversed_ids = list(reversed(deployment_ids))

        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        # Request with original order
        response1 = await client_with_real_docket.post(
            "/deployments/get_scheduled_flow_runs",
            json={"deployment_ids": deployment_ids},
        )
        assert response1.status_code == status.HTTP_200_OK

        # Request with reversed order - should not create a new task
        response2 = await client_with_real_docket.post(
            "/deployments/get_scheduled_flow_runs",
            json={"deployment_ids": reversed_ids},
        )
        assert response2.status_code == status.HTTP_200_OK

        final_snapshot = await real_docket.snapshot()
        new_tasks = final_snapshot.total_tasks - initial_task_count

        # Should only have 1 task because both requests generate the same key
        assert new_tasks == 1, (
            f"Expected 1 task (order-independent keys), but got {new_tasks}. "
            "Requests with same IDs in different order should produce same key."
        )

    async def test_flow_run_delete_queues_single_task(
        self,
        flow_run,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        """
        Verify that deleting a flow run queues exactly one log deletion task.
        """
        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        response = await client_with_real_docket.delete(f"/flow_runs/{flow_run.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        final_snapshot = await real_docket.snapshot()
        new_tasks = final_snapshot.total_tasks - initial_task_count

        assert new_tasks == 1, f"Expected 1 task, but got {new_tasks}"

        expected_key = f"delete_flow_run_logs:{flow_run.id}"
        # Include both future (queued) and running tasks since the worker may have
        # already started processing some tasks by the time we take the snapshot
        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        assert expected_key in task_keys

    async def test_task_run_delete_queues_single_task(
        self,
        task_run,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        """
        Verify that deleting a task run queues exactly one log deletion task.
        """
        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        response = await client_with_real_docket.delete(f"/task_runs/{task_run.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        final_snapshot = await real_docket.snapshot()
        new_tasks = final_snapshot.total_tasks - initial_task_count

        assert new_tasks == 1, f"Expected 1 task, but got {new_tasks}"

        expected_key = f"delete_task_run_logs:{task_run.id}"
        # Include both future (queued) and running tasks since the worker may have
        # already started processing some tasks by the time we take the snapshot
        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        assert expected_key in task_keys
