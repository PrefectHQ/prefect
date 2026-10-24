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
import sqlalchemy as sa
from docket import Docket, Worker
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect._internal.compatibility.starlette import status
from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface, orm_models
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.events.schemas.events import Event
from prefect.server.schemas.statuses import DeploymentStatus, WorkQueueStatus
from prefect.server.services import foreman
from prefect.server.services.cancellation_cleanup import cancelling_timeout_check_key
from prefect.settings import (
    PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED,
    PREFECT_SERVER_SERVICES_FOREMAN_DEPLOYMENT_LAST_POLLED_TIMEOUT_SECONDS,
    get_current_settings,
    temporary_settings,
)
from prefect.types._datetime import now

pytestmark = pytest.mark.clear_db


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
    async def queue_deployment(
        self,
        session: AsyncSession,
        flow: orm_models.Flow,
        work_pool: orm_models.WorkPool,
    ) -> orm_models.Deployment:
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                name="queue-deployment",
                flow_id=flow.id,
                work_queue_id=work_pool.default_queue_id,
            ),
        )
        assert deployment is not None
        await session.commit()
        return deployment

    @pytest.mark.parametrize("poll_kind", ["pool", "polled", "ready"])
    async def test_large_queue_set_records_polls_within_bind_limit(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
        work_pool: orm_models.WorkPool,
        client_with_real_docket: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        poll_kind: str,
    ):
        budget = 100
        queue_ids = [work_pool.default_queue_id, *(uuid4() for _ in range(budget))]
        await session.execute(
            sa.insert(db.WorkQueue),
            [
                {"id": queue_id, "name": str(queue_id), "work_pool_id": work_pool.id}
                for queue_id in queue_ids[1:]
            ],
        )
        await session.commit()
        polled = now("UTC")
        monkeypatch.setattr(models.work_queues, "now", lambda _: polled)
        monkeypatch.setattr(
            models.work_queues, "get_max_query_parameters", lambda: budget
        )
        monkeypatch.setattr(
            models.work_queues, "PrefectServerEventsClient", AssertingEventsClient
        )
        AssertingEventsClient.reset()

        def enforce_bind_limit(
            conn: sa.Connection,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: sa.engine.ExecutionContext,
            executemany: bool,
        ) -> None:
            assert len(parameters) <= budget

        engine = await db.engine()
        sa.event.listen(engine.sync_engine, "before_cursor_execute", enforce_bind_limit)
        try:
            if poll_kind == "pool":
                response = await client_with_real_docket.post(
                    f"/work_pools/{work_pool.name}/get_scheduled_flow_runs", json={}
                )
                assert response.status_code == 200
            else:
                await models.work_queues.mark_work_queues_ready(
                    db=db,
                    polled_work_queue_ids=queue_ids if poll_kind == "polled" else [],
                    ready_work_queue_ids=queue_ids if poll_kind == "ready" else [],
                )
        finally:
            sa.event.remove(
                engine.sync_engine, "before_cursor_execute", enforce_bind_limit
            )

        queues = (
            await session.scalars(
                sa.select(db.WorkQueue).where(db.WorkQueue.work_pool_id == work_pool.id)
            )
        ).all()
        assert len(queues) == len(queue_ids)
        assert all(queue.last_polled == polled for queue in queues)
        assert all(
            queue.status
            == (
                WorkQueueStatus.READY
                if poll_kind == "ready"
                else WorkQueueStatus.NOT_READY
            )
            for queue in queues
        )
        events = [
            event for client in AssertingEventsClient.all for event in client.events
        ]
        assert len(events) == (len(queue_ids) if poll_kind == "ready" else 0)
        if poll_kind == "ready":
            assert {event.resource.id for event in events} == {
                f"prefect.work-queue.{queue_id}" for queue_id in queue_ids
            }
            assert all(event.event == "prefect.work-queue.ready" for event in events)

    @pytest.mark.parametrize("poll_kind", ["queue", "pool"])
    async def test_deduplicated_poll_preserves_latest_heartbeat(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
        queue_deployment: orm_models.Deployment,
        work_pool: orm_models.WorkPool,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        poll_kind: str,
    ):
        queue_id = queue_deployment.work_queue_id
        assert queue_id is not None
        route = (
            f"/work_queues/{queue_id}/get_runs"
            if poll_kind == "queue"
            else f"/work_pools/{work_pool.name}/get_scheduled_flow_runs"
        )
        start = now("UTC")
        clock = start
        for module in (models.work_queues, models.deployments, foreman):
            monkeypatch.setattr(module, "now", lambda _: clock)
        await models.deployments.mark_deployments_ready(
            db=db, deployment_ids=[queue_deployment.id]
        )

        with temporary_settings(
            {PREFECT_SERVER_SERVICES_FOREMAN_DEPLOYMENT_LAST_POLLED_TIMEOUT_SECONDS: 60}
        ):
            for elapsed in (0, 25):
                clock = start + timedelta(seconds=elapsed)
                response = await client_with_real_docket.post(route, json={})
                assert response.status_code == 200
            assert (await real_docket.snapshot()).total_tasks == 2
            queue = await session.get(db.WorkQueue, queue_id)
            assert queue is not None
            await session.refresh(queue)
            assert queue.last_polled == clock

            # The deployment task can finish while the queue task is still delayed.
            clock = start + timedelta(seconds=26)
            await models.deployments.mark_deployments_ready(
                db=db, work_queue_ids=[queue_id], skip_recently_polled=True
            )
            await session.refresh(queue_deployment)
            assert queue_deployment.last_polled == start
            for elapsed, expected in (
                (65, DeploymentStatus.READY),
                (86, DeploymentStatus.NOT_READY),
            ):
                clock = start + timedelta(seconds=elapsed)
                await foreman._mark_deployments_as_not_ready(
                    db=db, deployment_last_polled_timeout_seconds=60
                )
                await session.refresh(queue_deployment)
                assert queue_deployment.status == expected

    @pytest.mark.parametrize("poll_kind", ["queue", "pool"])
    async def test_deployment_enqueue_failure_does_not_repeat_queue_event(
        self,
        session: AsyncSession,
        queue_deployment: orm_models.Deployment,
        work_pool: orm_models.WorkPool,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        poll_kind: str,
    ):
        queue_id = queue_deployment.work_queue_id
        route = (
            f"/work_queues/{queue_id}/get_runs"
            if poll_kind == "queue"
            else f"/work_pools/{work_pool.name}/get_scheduled_flow_runs"
        )
        monkeypatch.setattr(
            models.work_queues, "PrefectServerEventsClient", AssertingEventsClient
        )
        add = real_docket.add

        def fail_deployment_enqueue(function: Any, *args: Any, **kwargs: Any) -> Any:
            if function is models.deployments.mark_deployments_ready:

                async def reject(*args: Any, **kwargs: Any) -> None:
                    raise ConnectionError("deployment enqueue failed")

                return reject
            return add(function, *args, **kwargs)

        AssertingEventsClient.reset()
        async with Worker(real_docket) as worker:
            with monkeypatch.context() as patcher:
                patcher.setattr(real_docket, "add", fail_deployment_enqueue)
                for _ in range(5):
                    with pytest.raises(
                        ConnectionError, match="deployment enqueue failed"
                    ):
                        await client_with_real_docket.post(route, json={})
                    await worker.run_until_finished()
            assert [
                event.event
                for client in AssertingEventsClient.all
                for event in client.events
            ] == ["prefect.work-queue.ready"]
            response = await client_with_real_docket.post(route, json={})
            assert response.status_code == 200
            await worker.run_until_finished()

        await session.refresh(queue_deployment)
        assert queue_deployment.status == DeploymentStatus.READY
        assert sorted(
            event.event
            for client in AssertingEventsClient.all
            for event in client.events
        ) == ["prefect.deployment.ready", "prefect.work-queue.ready"]

    @pytest.mark.parametrize("failure_table", ["work_queue", "deployment"])
    async def test_poll_write_failure_preserves_independent_work(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
        queue_deployment: orm_models.Deployment,
        work_pool: orm_models.WorkPool,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        failure_table: str,
    ):
        monkeypatch.setattr(
            models.work_queues, "PrefectServerEventsClient", AssertingEventsClient
        )

        def fail_update(
            conn: sa.Connection,
            cursor: Any,
            statement: str,
            parameters: Any,
            context: sa.engine.ExecutionContext,
            executemany: bool,
        ) -> None:
            if (
                context.isupdate
                and context.compiled.statement.table.name == failure_table
            ):
                raise RuntimeError("poll write failed")

        engine = await db.engine()
        AssertingEventsClient.reset()
        sa.event.listen(engine.sync_engine, "before_cursor_execute", fail_update)
        try:
            async with Worker(real_docket) as worker:
                route = f"/work_pools/{work_pool.name}/get_scheduled_flow_runs"
                if failure_table == "work_queue":
                    with pytest.raises(RuntimeError, match="poll write failed"):
                        await client_with_real_docket.post(route, json={})
                    assert (await real_docket.snapshot()).total_tasks == 0
                else:
                    response = await client_with_real_docket.post(route, json={})
                    assert response.status_code == 200
                    await worker.run_until_finished()
        finally:
            sa.event.remove(engine.sync_engine, "before_cursor_execute", fail_update)

        queue = await session.get(db.WorkQueue, queue_deployment.work_queue_id)
        assert queue is not None
        await session.refresh(queue)
        await session.refresh(queue_deployment)
        assert queue_deployment.status == DeploymentStatus.NOT_READY
        assert queue.status == (
            WorkQueueStatus.READY
            if failure_table == "deployment"
            else WorkQueueStatus.NOT_READY
        )
        assert [
            event.event
            for client in AssertingEventsClient.all
            for event in client.events
        ] == (["prefect.work-queue.ready"] if failure_table == "deployment" else [])

    async def test_deployment_work_survives_queue_event_failure(
        self,
        session: AsyncSession,
        queue_deployment: orm_models.Deployment,
        work_pool: orm_models.WorkPool,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        class FailingQueueEventsClient(AssertingEventsClient):
            async def emit(self, event: Event) -> Event:
                raise ConnectionError("queue event failed")

        monkeypatch.setattr(
            models.work_queues, "PrefectServerEventsClient", FailingQueueEventsClient
        )
        AssertingEventsClient.reset()
        response = await client_with_real_docket.post(
            f"/work_pools/{work_pool.name}/get_scheduled_flow_runs", json={}
        )
        assert response.status_code == 200
        async with Worker(real_docket) as worker:
            await worker.run_until_finished()
        await session.refresh(queue_deployment)
        assert queue_deployment.status == DeploymentStatus.READY
        assert [
            event.event
            for client in AssertingEventsClient.all
            for event in client.events
        ] == ["prefect.deployment.ready"]

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

    async def test_cancelling_flow_run_state_queues_single_timeout_check(
        self,
        flow_run,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        running_response = await client_with_real_docket.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json={"state": {"type": "RUNNING", "name": "Running"}},
        )
        assert running_response.status_code == status.HTTP_201_CREATED

        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        with temporary_settings(
            {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED: True}
        ):
            cancelling_response = await client_with_real_docket.post(
                f"/flow_runs/{flow_run.id}/set_state",
                json={"state": {"type": "CANCELLING", "name": "Cancelling"}},
            )
        assert cancelling_response.status_code == status.HTTP_201_CREATED

        final_snapshot = await real_docket.snapshot()
        new_tasks = final_snapshot.total_tasks - initial_task_count
        assert new_tasks == 1

        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        assert cancelling_timeout_check_key(flow_run.id) in task_keys

    async def test_bulk_cancelling_flow_run_state_queues_timeout_check(
        self,
        flow_run,
        real_docket: Docket,
        client_with_real_docket: AsyncClient,
    ):
        running_response = await client_with_real_docket.post(
            f"/flow_runs/{flow_run.id}/set_state",
            json={"state": {"type": "RUNNING", "name": "Running"}},
        )
        assert running_response.status_code == status.HTTP_201_CREATED

        initial_snapshot = await real_docket.snapshot()
        initial_task_count = initial_snapshot.total_tasks

        with temporary_settings(
            {PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED: True}
        ):
            cancelling_response = await client_with_real_docket.post(
                "/flow_runs/bulk_set_state",
                json={
                    "flow_runs": {"id": {"any_": [str(flow_run.id)]}},
                    "state": {"type": "CANCELLING", "name": "Cancelling"},
                },
            )
        assert cancelling_response.status_code == status.HTTP_200_OK
        results = cancelling_response.json()["results"]
        assert len(results) == 1
        assert results[0]["status"] == "ACCEPT"

        final_snapshot = await real_docket.snapshot()
        new_tasks = final_snapshot.total_tasks - initial_task_count
        assert new_tasks == 1

        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        assert cancelling_timeout_check_key(flow_run.id) in task_keys

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

        # Queue events and deployment updates have separate deduplicated tasks.
        new_tasks = final_snapshot.total_tasks - initial_task_count
        assert new_tasks == 2

        # Verify the tasks have the expected keys
        # Include both future (queued) and running tasks since the worker may have
        # already started processing some tasks by the time we take the snapshot
        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        assert f"mark_work_queues_ready:{work_queue.id}" in task_keys
        assert f"mark_deployments_ready:work_queue:{work_queue.id}" in task_keys

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

        # Queue events and deployment updates have separate deduplicated tasks.
        assert new_tasks == 2

        # Include both future (queued) and running tasks since the worker may have
        # already started processing some tasks by the time we take the snapshot
        task_keys = {task.key for task in final_snapshot.future}
        task_keys.update(task.key for task in final_snapshot.running)
        assert f"mark_work_queues_ready:work_pool:{work_pool.id}" in task_keys
        assert f"mark_deployments_ready:work_pool:{work_pool.id}" in task_keys

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
