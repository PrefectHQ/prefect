"""
Tests for docket task keys in API handlers.

These tests verify that API handlers use consistent, deterministic task keys when
scheduling background docket tasks. Task keys ensure at-most-once execution semantics,
preventing duplicate task execution when multiple API servers process the same request.

See: https://github.com/PrefectHQ/prefect/pull/19936#issuecomment-3744457809
"""

from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from docket import Docket
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.compatibility.starlette import status
from prefect.client.base import app_lifespan_context
from prefect.server import models, schemas
from prefect.server.api.server import create_app
from prefect.server.schemas.statuses import DeploymentStatus
from prefect.settings import PREFECT_SERVER_DOCKET_NAME, temporary_settings


class MockDocket:
    """A mock Docket that captures task keys passed to add()."""

    def __init__(self):
        self.captured_keys: list[str] = []
        self.captured_funcs: list[str] = []

    def add(self, func, key=None):
        if key:
            self.captured_keys.append(key)
        self.captured_funcs.append(
            func.__name__ if hasattr(func, "__name__") else str(func)
        )
        # Return a callable that accepts the task arguments and returns an async mock
        return AsyncMock(return_value=None)

    def register(self, func):
        """Mock register method - no-op."""
        pass


@pytest.fixture
def mock_docket():
    """Fixture that provides a mock docket instance."""
    return MockDocket()


@pytest.fixture
def app_with_mock_docket(mock_docket: MockDocket) -> FastAPI:
    """Create an app with the docket set to our mock on the app state."""
    unique_name = f"test-docket-{uuid4().hex[:8]}"
    with temporary_settings({PREFECT_SERVER_DOCKET_NAME: unique_name}):
        app = create_app(ephemeral=True)

    # Set the mock docket directly on app state (this is where the dependency reads from)
    # The app has a nested structure: app -> api_app
    # We need to set it on the api_app which handles the /api routes
    app.api_app.state.docket = mock_docket
    return app


@pytest.fixture
async def client_with_mock_docket(
    app_with_mock_docket: FastAPI,
) -> AsyncGenerator[AsyncClient, Any]:
    """Yield a test client with mocked docket."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app_with_mock_docket), base_url="https://test/api"
    ) as async_client:
        yield async_client


class TestDocketTaskKeysWorkQueues:
    """Tests for docket task keys in work_queues.py API handlers."""

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

    async def test_read_work_queue_runs_uses_deterministic_task_keys(
        self,
        work_queue,
        mock_docket: MockDocket,
        client_with_mock_docket: AsyncClient,
    ):
        """
        Verify that reading work queue runs uses deterministic task keys based on
        the work queue ID, ensuring at-most-once execution for duplicate requests.
        """
        # Make two identical requests
        for _ in range(2):
            response = await client_with_mock_docket.post(
                f"/work_queues/{work_queue.id}/get_runs",
            )
            assert response.status_code == status.HTTP_200_OK

        # Verify we captured keys for both mark_work_queues_ready and mark_deployments_ready
        assert len(mock_docket.captured_keys) == 4  # 2 requests * 2 docket calls each

        # Verify keys are deterministic (same key used for both requests)
        assert (
            mock_docket.captured_keys[0] == mock_docket.captured_keys[2]
        )  # mark_work_queues_ready
        assert (
            mock_docket.captured_keys[1] == mock_docket.captured_keys[3]
        )  # mark_deployments_ready

        # Verify keys contain work_queue_id
        assert str(work_queue.id) in mock_docket.captured_keys[0]
        assert str(work_queue.id) in mock_docket.captured_keys[1]

        # Verify key format
        assert mock_docket.captured_keys[0] == f"mark_work_queues_ready:{work_queue.id}"
        assert (
            mock_docket.captured_keys[1]
            == f"mark_deployments_ready:work_queue:{work_queue.id}"
        )


class TestDocketTaskKeysWorkers:
    """Tests for docket task keys in workers.py API handlers."""

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

    async def test_get_scheduled_flow_runs_uses_deterministic_task_keys(
        self,
        work_pool,
        mock_docket: MockDocket,
        client_with_mock_docket: AsyncClient,
    ):
        """
        Verify that getting scheduled flow runs uses deterministic task keys based on
        the work pool ID, ensuring at-most-once execution for duplicate requests.
        """
        # Make two identical requests
        for _ in range(2):
            response = await client_with_mock_docket.post(
                f"/work_pools/{work_pool.name}/get_scheduled_flow_runs",
                json={},
            )
            assert response.status_code == status.HTTP_200_OK

        # Verify we captured keys for both mark_work_queues_ready and mark_deployments_ready
        assert len(mock_docket.captured_keys) == 4  # 2 requests * 2 docket calls each

        # Verify keys are deterministic (same key used for both requests)
        assert (
            mock_docket.captured_keys[0] == mock_docket.captured_keys[2]
        )  # mark_work_queues_ready
        assert (
            mock_docket.captured_keys[1] == mock_docket.captured_keys[3]
        )  # mark_deployments_ready

        # Verify keys contain work_pool_id
        assert str(work_pool.id) in mock_docket.captured_keys[0]
        assert str(work_pool.id) in mock_docket.captured_keys[1]

        # Verify key format
        assert (
            mock_docket.captured_keys[0]
            == f"mark_work_queues_ready:work_pool:{work_pool.id}"
        )
        assert (
            mock_docket.captured_keys[1]
            == f"mark_deployments_ready:work_pool:{work_pool.id}"
        )


class TestDocketTaskKeysDeployments:
    """Tests for docket task keys in deployments.py API handlers."""

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

    async def test_get_scheduled_flow_runs_for_deployments_uses_deterministic_task_keys(
        self,
        deployments,
        mock_docket: MockDocket,
        client_with_mock_docket: AsyncClient,
    ):
        """
        Verify that getting scheduled flow runs for deployments uses deterministic
        task keys based on sorted deployment IDs.
        """
        deployment_ids = [str(d.id) for d in deployments]

        # Make two identical requests
        for _ in range(2):
            response = await client_with_mock_docket.post(
                "/deployments/get_scheduled_flow_runs",
                json={"deployment_ids": deployment_ids},
            )
            assert response.status_code == status.HTTP_200_OK

        # Verify we captured keys for mark_deployments_ready
        assert len(mock_docket.captured_keys) == 2  # 2 requests * 1 docket call each

        # Verify keys are deterministic (same key used for both requests)
        assert mock_docket.captured_keys[0] == mock_docket.captured_keys[1]

        # Verify key contains sorted deployment IDs
        sorted_ids = ",".join(str(d) for d in sorted(UUID(id) for id in deployment_ids))
        assert (
            mock_docket.captured_keys[0]
            == f"mark_deployments_ready:deployments:{sorted_ids}"
        )

    async def test_get_scheduled_flow_runs_key_is_order_independent(
        self,
        deployments,
        mock_docket: MockDocket,
        client_with_mock_docket: AsyncClient,
    ):
        """
        Verify that the task key is the same regardless of the order deployment IDs
        are provided in the request.
        """
        deployment_ids = [str(d.id) for d in deployments]
        reversed_ids = list(reversed(deployment_ids))

        # Request with original order
        response1 = await client_with_mock_docket.post(
            "/deployments/get_scheduled_flow_runs",
            json={"deployment_ids": deployment_ids},
        )
        assert response1.status_code == status.HTTP_200_OK

        # Request with reversed order
        response2 = await client_with_mock_docket.post(
            "/deployments/get_scheduled_flow_runs",
            json={"deployment_ids": reversed_ids},
        )
        assert response2.status_code == status.HTTP_200_OK

        # Keys should be identical regardless of input order
        assert len(mock_docket.captured_keys) == 2
        assert mock_docket.captured_keys[0] == mock_docket.captured_keys[1]


class TestDocketTaskKeysFlowRuns:
    """Tests for docket task keys in flow_runs.py API handlers."""

    @pytest.fixture
    async def flow(self, session: AsyncSession):
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-{uuid4().hex[:8]}"),
        )
        await session.commit()
        return flow

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

    async def test_delete_flow_run_uses_deterministic_task_key(
        self,
        flow_run,
        mock_docket: MockDocket,
        client_with_mock_docket: AsyncClient,
    ):
        """
        Verify that deleting a flow run uses a deterministic task key based on
        the flow run ID.
        """
        response = await client_with_mock_docket.delete(f"/flow_runs/{flow_run.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify we captured the key for delete_flow_run_logs
        assert len(mock_docket.captured_keys) == 1
        assert mock_docket.captured_keys[0] == f"delete_flow_run_logs:{flow_run.id}"


class TestDocketTaskKeysTaskRuns:
    """Tests for docket task keys in task_runs.py API handlers."""

    @pytest.fixture
    async def flow(self, session: AsyncSession):
        flow = await models.flows.create_flow(
            session=session,
            flow=schemas.core.Flow(name=f"test-flow-{uuid4().hex[:8]}"),
        )
        await session.commit()
        return flow

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

    async def test_delete_task_run_uses_deterministic_task_key(
        self,
        task_run,
        mock_docket: MockDocket,
        client_with_mock_docket: AsyncClient,
    ):
        """
        Verify that deleting a task run uses a deterministic task key based on
        the task run ID.
        """
        response = await client_with_mock_docket.delete(f"/task_runs/{task_run.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify we captured the key for delete_task_run_logs
        assert len(mock_docket.captured_keys) == 1
        assert mock_docket.captured_keys[0] == f"delete_task_run_logs:{task_run.id}"


# =============================================================================
# Integration tests using real Docket instance
# =============================================================================
# These tests verify the actual at-most-once execution behavior by inspecting
# the Docket task queue after making duplicate API requests.


@pytest.fixture
async def app_with_real_docket() -> AsyncGenerator[FastAPI, Any]:
    """Create an app with a real Docket instance via lifespan context."""
    unique_name = f"test-docket-{uuid4().hex[:8]}"
    with temporary_settings({PREFECT_SERVER_DOCKET_NAME: unique_name}):
        app = create_app(ephemeral=True)
        async with app_lifespan_context(app):
            yield app


@pytest.fixture
async def client_with_real_docket(
    app_with_real_docket: FastAPI,
) -> AsyncGenerator[AsyncClient, Any]:
    """Yield a test client with a real Docket instance."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app_with_real_docket), base_url="https://test/api"
    ) as async_client:
        yield async_client


@pytest.fixture
def real_docket(app_with_real_docket: FastAPI) -> Docket:
    """Get the real Docket instance from the app."""
    return app_with_real_docket.api_app.state.docket


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
        task_keys = {task.key for task in final_snapshot.future}
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

        task_keys = {task.key for task in final_snapshot.future}
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
        task_keys = {task.key for task in final_snapshot.future}
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
        task_keys = {task.key for task in final_snapshot.future}
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
        task_keys = {task.key for task in final_snapshot.future}
        assert expected_key in task_keys
