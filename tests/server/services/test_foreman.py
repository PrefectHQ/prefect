from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import uuid4

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.statuses import DeploymentStatus
from prefect.server.services.foreman import Foreman
from prefect.settings import (
    PREFECT_API_SERVICES_FOREMAN_FALLBACK_HEARTBEAT_INTERVAL_SECONDS,
    PREFECT_API_SERVICES_FOREMAN_INACTIVITY_HEARTBEAT_MULTIPLE,
)

if TYPE_CHECKING:
    from prefect.server.database.orm_models import (
        ORMDeployment,
        ORMWorkPool,
        ORMWorkQueue,
    )


@pytest.fixture(autouse=True)
def patch_events_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "prefect.server.models.work_queues.PrefectServerEventsClient",
        AssertingEventsClient,
    )
    monkeypatch.setattr(
        "prefect.server.models.workers.PrefectServerEventsClient",
        AssertingEventsClient,
    )


@pytest.fixture
async def ready_work_pool(session: AsyncSession):
    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(name="ready-work-pool", type="test"),
    )
    work_pool.status = schemas.statuses.WorkPoolStatus.READY
    await session.commit()
    return work_pool


@pytest.fixture
async def not_ready_work_pool(session: AsyncSession):
    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="ready-work-pool",
            type="test",
        ),
    )
    work_pool.status = schemas.statuses.WorkPoolStatus.NOT_READY
    await session.commit()
    return work_pool


@pytest.fixture
async def paused_work_pool(session: AsyncSession):
    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="ready-work-pool", type="test", is_paused=True
        ),
    )
    await session.commit()
    return work_pool


@db_injector
async def create_online_worker_with_old_heartbeat(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool: "ORMWorkPool",
    heartbeat_interval_seconds: Optional[int] = 60,
):
    worker_name = "online-worker-with-old-heartbeat"
    last_heartbeat_time = datetime.now(timezone.utc) - timedelta(
        seconds=PREFECT_API_SERVICES_FOREMAN_INACTIVITY_HEARTBEAT_MULTIPLE.value()
        * (
            heartbeat_interval_seconds
            or PREFECT_API_SERVICES_FOREMAN_FALLBACK_HEARTBEAT_INTERVAL_SECONDS.value()
        )
    )

    values = dict(
        work_pool_id=work_pool.id,
        name=worker_name,
        last_heartbeat_time=last_heartbeat_time,
        status=schemas.statuses.WorkerStatus.ONLINE,
    )

    if heartbeat_interval_seconds:
        values["heartbeat_interval_seconds"] = heartbeat_interval_seconds

    insert_stmt = sa.insert(db.Worker).values(**values)

    await session.execute(insert_stmt)

    await session.commit()

    workers = await models.workers.read_workers(
        session=session, work_pool_id=work_pool.id
    )

    return next(worker for worker in workers if worker.name == worker_name)


async def create_online_worker_with_new_heartbeat(
    session: AsyncSession, work_pool: "ORMWorkPool"
):
    worker_name = "online-worker-with-new-heartbeat"
    heartbeat_interval_seconds = 60
    await models.workers.worker_heartbeat(
        session=session,
        work_pool_id=work_pool.id,
        worker_name=worker_name,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
    )

    await session.commit()

    workers = await models.workers.read_workers(
        session=session, work_pool_id=work_pool.id
    )

    return next(worker for worker in workers if worker.name == worker_name)


@db_injector
async def create_deployment_with_old_last_polled_time(
    db: PrefectDBInterface,
    session: AsyncSession,
    suffix: str = "",
) -> "ORMDeployment":
    flow_1 = await models.flows.create_flow(
        session=session,
        flow=schemas.core.Flow(
            name=f"test-flow-{suffix}",
        ),
    )
    assert flow_1

    await session.commit()

    work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name=f"test-wp-{suffix}",
        ),
    )

    work_pool_id = work_pool.id

    values = dict(name=f"test-wq-{suffix}", work_pool_id=str(work_pool_id))

    insert_stmt = sa.insert(db.WorkQueue).values(**values)

    await session.execute(insert_stmt)

    await session.commit()

    work_queue = await models.workers.read_work_queue_by_name(
        session=session,
        work_queue_name=f"test-wq-{suffix}",
        work_pool_name=f"test-wp-{suffix}",
    )

    assert work_queue
    work_queue_id = work_queue.id

    deployment_name = f"deployment-with-old-last-polled-time-{suffix}"

    last_polled = datetime.now(timezone.utc) - timedelta(60)
    values = dict(
        name=deployment_name,
        flow_id=str(flow_1.id),
        work_queue_name=f"test-wq-{suffix}",
        work_queue_id=str(work_queue_id),
        last_polled=last_polled,
        status=DeploymentStatus.READY,
    )

    insert_stmt = sa.insert(db.Deployment).values(**values)
    await session.execute(insert_stmt)
    await session.commit()

    deployment = await models.deployments.read_deployment_by_name(
        session=session,
        name=deployment_name,
        flow_name=f"test-flow-{suffix}",
    )
    assert deployment
    return deployment


@db_injector
async def create_deployment_with_new_last_polled_time(
    db: PrefectDBInterface, session: AsyncSession
) -> "ORMDeployment":
    flow_2 = await models.flows.create_flow(
        session=session,
        flow=schemas.core.Flow(
            name="test-flow-1",
        ),
    )
    assert flow_2

    await session.commit()

    deployment_name = "deployment-with-new-last-polled-time"

    last_polled = datetime.now(timezone.utc)

    deployment_values = dict(
        name=deployment_name,
        flow_id=str(flow_2.id),
        last_polled=last_polled,
        status=schemas.statuses.DeploymentStatus.READY,
    )

    insert_stmt = sa.insert(db.Deployment).values(**deployment_values)
    await session.execute(insert_stmt)
    await session.commit()

    deployment = await models.deployments.read_deployment_by_name(
        session=session,
        name=deployment_name,
        flow_name=f"{flow_2.name}",
    )
    assert deployment
    return deployment


class TestForeman:
    async def test_status_update_when_worker_has_old_heartbeat(
        self,
        session: AsyncSession,
        ready_work_pool,
        client,
    ):
        """
        Workers that haven't sent a heartbeat in greater than
        INACTIVITY_HEARTBEAT_MULTIPLE * heartbeat_interval_seconds
        seconds should have their status set to OFFLINE.

        When the worker that is marked offline is the only worker
        in a work pool, the work pool should be marked as NOT_READY.
        """
        await create_online_worker_with_old_heartbeat(session, ready_work_pool)
        await session.commit()

        await Foreman().run_once()

        # Check worker is marked offline
        workers_response = await client.post(
            f"/work_pools/{ready_work_pool.name}/workers/filter"
        )

        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["status"] == "OFFLINE"

        # Check work pool is marked not_ready
        work_pools_response = await client.get(f"/work_pools/{ready_work_pool.name}")

        assert work_pools_response.json()["status"] == "NOT_READY"

        assert AssertingEventsClient.last
        events = [event for item in AssertingEventsClient.all for event in item.events]
        assert len(events) == 1

        event = events[0]
        assert event.event == "prefect.work-pool.not-ready"
        assert event.resource.id == f"prefect.work-pool.{ready_work_pool.id}"
        assert event.resource.name == ready_work_pool.name
        assert event.resource["prefect.work-pool.type"] == "test"

    async def test_work_pool_status_update_with_multiple_workers(
        self,
        ready_work_pool,
        session: AsyncSession,
        client,
    ):
        """
        When a work pool has multiple workers, and one of them has an old heartbeat,
        the work pools should remain READY.
        """
        old_heartbeat_worker = await create_online_worker_with_old_heartbeat(
            session, ready_work_pool
        )
        assert old_heartbeat_worker.status == schemas.statuses.WorkerStatus.ONLINE

        new_heartbeat_worker = await create_online_worker_with_new_heartbeat(
            session, ready_work_pool
        )
        assert new_heartbeat_worker.status == schemas.statuses.WorkerStatus.ONLINE

        assert ready_work_pool.status == schemas.statuses.WorkPoolStatus.READY
        await session.commit()

        await Foreman().run_once()

        # Check one worker is marked offline
        workers_response = await client.post(
            f"/work_pools/{ready_work_pool.name}/workers/filter"
        )

        assert len(workers_response.json()) == 2
        old_heartbeat_worker = next(
            worker
            for worker in workers_response.json()
            if worker["name"] == old_heartbeat_worker.name
        )
        new_heartbeat_worker = next(
            worker
            for worker in workers_response.json()
            if worker["name"] == new_heartbeat_worker.name
        )
        assert new_heartbeat_worker["status"] == "ONLINE"
        assert old_heartbeat_worker["status"] == "OFFLINE"

        # Check work pool is marked ready
        work_pools_response = await client.get(f"/work_pools/{ready_work_pool.name}")

        assert work_pools_response.json()["status"] == "READY"

    async def test_foreman_does_not_update_status_of_paused_work_pools(
        self,
        paused_work_pool,
        client,
    ):
        """
        Foreman should not update the status of PAUSED work pools. The work pool
        will be given the correct status by the orchestrator when it is unpaused.
        """
        assert paused_work_pool.status == schemas.statuses.WorkPoolStatus.PAUSED

        await Foreman().run_once()

        # Check work pool is still marked paused
        work_pool_response = await client.get(f"/work_pools/{paused_work_pool.name}")

        assert work_pool_response.json()["status"] == "PAUSED"

    async def test_foreman_does_not_update_not_ready_work_pools(
        self,
        db,
        not_ready_work_pool,
        session: AsyncSession,
        client,
    ):
        """
        A somewhat contrived test where a NOT_READY work pool has an online worker
        with a recent heartbeat. The work pool should remain NOT_READY because it
        is not Foreman's responsibility to mark work pools as READY.
        """
        # Purposely create a worker with a recent heartbeat without using the
        # worker_heartbeat function to avoid the work pool being marked as READY
        worker_name = "online-worker-with-old-heartbeat"
        heartbeat_interval_seconds = 60
        last_heartbeat_time = datetime.now(timezone.utc)

        values = dict(
            work_pool_id=not_ready_work_pool.id,
            name=worker_name,
            last_heartbeat_time=last_heartbeat_time,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            status=schemas.statuses.WorkerStatus.ONLINE,
        )

        insert_stmt = sa.insert(db.Worker).values(**values)

        await session.execute(insert_stmt)

        await session.commit()

        work_pool_response = await client.get(f"/work_pools/{not_ready_work_pool.name}")

        assert work_pool_response.json()["status"] == "NOT_READY"

        await Foreman().run_once()

        work_pool_response = await client.get(f"/work_pools/{not_ready_work_pool.name}")

    async def test_foreman_can_mark_workers_without_heartbeat_interval_offline(
        self,
        not_ready_work_pool,
        session: AsyncSession,
        client,
    ):
        """
        Workers that do not have a heartbeat interval should be marked offline
        if they have not sent a heartbeat by using the fallback heartbeat interval.
        """
        await create_online_worker_with_old_heartbeat(
            session=session,
            work_pool=not_ready_work_pool,
            heartbeat_interval_seconds=None,
        )
        await session.commit()

        await Foreman().run_once()

        # Check worker is marked offline
        workers_response = await client.post(
            f"/work_pools/{not_ready_work_pool.name}/workers/filter"
        )

        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["status"] == "OFFLINE"

    async def test_foreman_events_correctly_set_follows_on_events(
        self,
        session: AsyncSession,
        ready_work_pool,
        client,
    ):
        """
        Events should be properly ordered via follows when work pool status
        changes quickly in succession.
        """
        await create_online_worker_with_old_heartbeat(session, ready_work_pool)
        await session.commit()

        await Foreman().run_once()

        # Check worker is marked offline
        workers_response = await client.post(
            f"/work_pools/{ready_work_pool.name}/workers/filter"
        )

        assert len(workers_response.json()) == 1
        assert workers_response.json()[0]["status"] == "OFFLINE"

        # Check work pool is marked not_ready
        work_pools_response = await client.get(f"/work_pools/{ready_work_pool.name}")

        assert work_pools_response.json()["status"] == "NOT_READY"

        # Heartbeat a worker
        await client.post(
            f"/work_pools/{ready_work_pool.name}/workers/heartbeat",
            json=dict(name="test-worker"),
        )

        # Check work pool is marked ready
        work_pools_response = await client.get(f"/work_pools/{ready_work_pool.name}")

        assert work_pools_response.json()["status"] == "READY"

        await Foreman(inactivity_heartbeat_multiple=0).run_once()

        # Check work pool is marked not_ready
        work_pools_response = await client.get(f"/work_pools/{ready_work_pool.name}")

        assert work_pools_response.json()["status"] == "NOT_READY"

        events = [event for item in AssertingEventsClient.all for event in item.events]
        assert len(events) == 3

        for event in events:
            print(event.id, event.follows, event.event, event.resource.id)

        assert events[0].event == "prefect.work-pool.not-ready"
        assert events[0].follows is None
        assert events[1].event == "prefect.work-pool.ready"
        assert events[1].follows == events[0].id
        assert events[2].event == "prefect.work-pool.not-ready"
        assert events[2].follows == events[1].id

    async def test_status_update_when_deployment_has_old_last_polled_time(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ):
        deployment = await create_deployment_with_old_last_polled_time(session=session)
        assert deployment
        assert deployment.status == "READY"
        await session.commit()

        await Foreman().run_once()

        # Check deployment is marked not_ready
        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "NOT_READY"

        assert AssertingEventsClient.last
        events = [event for item in AssertingEventsClient.all for event in item.events]
        assert len(events) == 1

        event = events[0]
        assert event.event == "prefect.deployment.not-ready"
        assert event.resource.id == f"prefect.deployment.{deployment.id}"

        assert event.resource.name == deployment.name
        assert (
            event.related[0]["prefect.resource.id"]
            == f"prefect.flow.{deployment.flow_id}"
        )
        flow_response = await client.get(f"/flows/{deployment.flow_id}")
        assert flow_response.status_code == 200
        flow = flow_response.json()
        assert event.related[0]["prefect.resource.name"] == flow["name"]
        assert event.related[0]["prefect.resource.role"] == "flow"

        assert (
            event.related[1]["prefect.resource.id"]
            == f"prefect.work-queue.{deployment.work_queue_id}"
        )
        assert event.related[1]["prefect.resource.name"] == deployment.work_queue_name
        assert event.related[1]["prefect.resource.role"] == "work-queue"

        work_queue_response = await client.get(
            f"/work_queues/{deployment.work_queue_id}"
        )
        assert work_queue_response.status_code == 200
        work_queue = response.json()
        work_pool_name = work_queue["work_pool_name"]

        assert event.related[2]["prefect.resource.name"] == work_pool_name
        assert event.related[2]["prefect.resource.role"] == "work-pool"

    async def test_status_update_when_deployment_has_new_last_polled_time(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ):
        deployment = await create_deployment_with_new_last_polled_time(session=session)
        assert deployment
        assert deployment.status == "READY"

        await session.commit()

        await Foreman().run_once()

        # Check deployment remains ready
        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "READY"

        events = [event for item in AssertingEventsClient.all for event in item.events]
        assert len(events) == 0

    async def test_foreman_with_no_deployments_to_update(self):
        await Foreman().run_once()

        assert not AssertingEventsClient.last

    async def test_foreman_does_not_mark_deployments_with_recently_polled_work_queue(
        self, session: AsyncSession
    ):
        """
        Tests deployments with old last_polled time are not marked as not_ready
        if the work_queue has been polled recently. Handles cases where there are
        hoards of deployments on the same work queue.
        """
        deployment = await create_deployment_with_old_last_polled_time(session)
        assert deployment
        assert deployment.status == DeploymentStatus.READY
        assert deployment.last_polled is not None
        assert deployment.last_polled < (
            datetime.now(timezone.utc)
            - timedelta(seconds=Foreman()._deployment_last_polled_timeout_seconds)
        )

        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=deployment.work_queue_id,
            work_queue=schemas.actions.WorkQueueUpdate(
                last_polled=datetime.now(timezone.utc)
            ),
        )

        await session.commit()

        await Foreman().run_once()

        assert not AssertingEventsClient.last

        deployment = await models.deployments.read_deployment(
            session=session,
            deployment_id=deployment.id,
        )
        assert deployment is not None
        assert deployment.status == DeploymentStatus.READY


class TestForemanWorkQueueService:
    async def create_work_pool(self, session: AsyncSession) -> "ORMWorkPool":
        work_pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name=f"{uuid4()}",
            ),
        )

        await session.flush()

        return work_pool

    @db_injector
    async def create_work_queue(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
        wp: "ORMWorkPool",
        **wq_fields,
    ) -> "ORMWorkQueue":
        name = f"{uuid4()}"
        insert_stmt = sa.insert(db.WorkQueue).values(
            name=name, work_pool_id=wp.id, **wq_fields
        )
        await session.execute(insert_stmt)
        await session.commit()

        work_queue = await models.workers.read_work_queue_by_name(
            session=session,
            work_queue_name=name,
            work_pool_name=wp.name,
        )
        assert work_queue

        return work_queue

    @db_injector
    async def create_unpolled_work_queues(
        self,
        db: PrefectDBInterface,
        session: AsyncSession,
        foreman: Foreman,
        *,
        count: int,
    ) -> List["ORMWorkQueue"]:
        """
        Create 'count' work queues that have not been polled for longer
        than foreman's timeout settings.
        """
        wp = await self.create_work_pool(session)
        queues = []
        for _ in range(count):
            queue = await self.create_work_queue(
                session,
                wp,
                status=schemas.statuses.WorkQueueStatus.READY,
                last_polled=datetime.now(timezone.utc)
                - timedelta(
                    seconds=foreman._work_queue_last_polled_timeout_seconds + 5
                ),
            )
            queues.append(queue)
        return queues

    async def create_polled_work_queues(
        self,
        session: AsyncSession,
        foreman: Foreman,
        *,
        count: int,
    ) -> List["ORMWorkQueue"]:
        """
        Create 'count' work queues that have been polled within foreman's
        timeout settings.
        """
        wp = await self.create_work_pool(session)
        queues = []
        for _ in range(count):
            queue = await self.create_work_queue(
                session,
                wp,
                status=schemas.statuses.WorkQueueStatus.READY,
                last_polled=datetime.now(timezone.utc),
            )
            queues.append(queue)
        return queues

    @db_injector
    async def poll_work_queue_by_name(
        self, db: PrefectDBInterface, session: AsyncSession, name: str
    ):
        stmt = (
            sa.update(db.WorkQueue)
            .where(
                db.WorkQueue.name == name,
            )
            .values(last_polled=datetime.now(timezone.utc))
        )
        await session.execute(stmt)

        result = await session.execute(
            sa.select(db.WorkQueue).where(db.WorkQueue.name == name)
        )
        return result.scalars().all()

    async def test_foreman_updates_status_for_late_last_polled_time(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ):
        foreman = Foreman()

        wp = await self.create_work_pool(session)
        wq = await self.create_work_queue(
            session,
            wp,
            status=schemas.statuses.WorkQueueStatus.READY,
            last_polled=datetime.now(timezone.utc)
            - timedelta(seconds=foreman._work_queue_last_polled_timeout_seconds + 5),
        )
        assert wq.status == schemas.statuses.WorkQueueStatus.READY

        await session.commit()

        await foreman.run_once()

        wq_response = await client.get(f"/work_queues/{wq.id}")
        assert wq_response.status_code == 200
        assert wq_response.json()["status"] == "NOT_READY"

    async def test_foreman_updates_status_for_many_late_last_polled_times(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ):
        foreman = Foreman()

        work_queues = await self.create_unpolled_work_queues(session, foreman, count=3)
        assert all(
            q.status == schemas.statuses.WorkQueueStatus.READY for q in work_queues
        )
        await session.commit()

        await foreman.run_once()

        for wq in work_queues:
            wq_response = await client.get(f"/work_queues/{wq.id}")
            assert wq_response.status_code == 200
            assert wq_response.json()["status"] == "NOT_READY"

    async def test_foreman_updates_do_not_mark_ready(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ) -> None:
        foreman = Foreman()

        wq = (await self.create_unpolled_work_queues(session, foreman, count=1))[0]
        assert wq.status == schemas.statuses.WorkQueueStatus.READY
        await session.commit()

        await foreman.run_once()

        # Assert that the queue is marked as not ready
        wq_response = await client.get(f"/work_queues/{wq.id}")
        assert wq_response.status_code == 200
        assert wq_response.json()["status"] == "NOT_READY"

        # Update the last_polled time to be now
        await self.poll_work_queue_by_name(session, name=wq.name)
        await session.commit()

        await foreman.run_once()

        # Assert that queue is not marked as ready
        wq_response = await client.get(f"/work_queues/{wq.id}")
        assert wq_response.status_code == 200
        assert wq_response.json()["status"] == "NOT_READY"

    async def test_foreman_does_not_update_recently_polled(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ):
        foreman = Foreman()

        work_queues = await self.create_polled_work_queues(session, foreman, count=3)
        assert all(
            q.status == schemas.statuses.WorkQueueStatus.READY for q in work_queues
        )
        await session.commit()

        await foreman.run_once()

        # Assert that recently polled queues are unchanged
        for wq in work_queues:
            wq_response = await client.get(f"/work_queues/{wq.id}")
            assert wq_response.status_code == 200
            assert wq_response.json()["status"] == "READY"

    async def test_status_update_work_queue(
        self,
        session: AsyncSession,
        client: AsyncClient,
        ready_work_pool,
    ):
        """
        Foreman should be able to update the status of multiple work queues.
        """
        now = datetime.now(timezone.utc)

        wq_1 = await self.create_work_queue(
            session,
            ready_work_pool,
            status=schemas.statuses.WorkQueueStatus.READY,
            last_polled=now
            - timedelta(seconds=Foreman()._work_queue_last_polled_timeout_seconds + 5),
        )
        assert wq_1.status == schemas.statuses.WorkQueueStatus.READY

        wq_2 = await self.create_work_queue(
            session,
            ready_work_pool,
            status=schemas.statuses.WorkQueueStatus.READY,
            last_polled=now
            - timedelta(seconds=Foreman()._work_queue_last_polled_timeout_seconds + 4),
        )
        assert wq_2.status == schemas.statuses.WorkQueueStatus.READY

        await session.commit()

        await Foreman().run_once()

        # Check work queues are marked not_ready
        wq_response_1 = await client.get(f"/work_queues/{wq_1.id}")
        assert wq_response_1.status_code == 200
        assert wq_response_1.json()["status"] == "NOT_READY"

        wq_response_2 = await client.get(f"/work_queues/{wq_2.id}")
        assert wq_response_2.status_code == 200
        assert wq_response_2.json()["status"] == "NOT_READY"

        assert wq_response_1.json()["last_polled"] < wq_response_2.json()["last_polled"]

        events = [
            event
            for item in AssertingEventsClient.all
            for event in item.events
            if event.event.startswith("prefect.work-queue.")
        ]

        # Until work pool status events are emitted, we have 2 work queue status events
        assert len(events) == 2  # 2 work queue status events
        # assert (
        #     len(events) == 4
        # )  # 2 work queue status events and 2 work pool status events

        assert {(event.resource.id, event.resource.name) for event in events} == {
            (f"prefect.work-queue.{wq_1.id}", wq_1.name),
            (f"prefect.work-queue.{wq_2.id}", wq_2.name),
        }

        # check work queue 1 status event emitted
        wq_status_event_wp_1 = events[0]
        assert wq_status_event_wp_1.event == "prefect.work-queue.not-ready"
        assert (
            wq_status_event_wp_1.related[0]["prefect.resource.id"]
            == f"prefect.work-pool.{ready_work_pool.id}"
        )
        assert (
            wq_status_event_wp_1.related[0]["prefect.resource.name"]
            == ready_work_pool.name
        )
        assert wq_status_event_wp_1.related[0]["prefect.resource.role"] == "work-pool"

        # check work queue 2 status event emitted
        wq_status_event_wp_2 = events[1]
        assert wq_status_event_wp_2.event == "prefect.work-queue.not-ready"
        assert (
            wq_status_event_wp_2.related[0]["prefect.resource.id"]
            == f"prefect.work-pool.{ready_work_pool.id}"
        )
        assert (
            wq_status_event_wp_2.related[0]["prefect.resource.name"]
            == ready_work_pool.name
        )
        assert wq_status_event_wp_2.related[0]["prefect.resource.role"] == "work-pool"

    async def test_foreman_with_no_wqs_to_update(
        self,
        session: AsyncSession,
    ):
        foreman = Foreman()

        work_queues = await self.create_polled_work_queues(session, foreman, count=3)
        assert all(
            q.status == schemas.statuses.WorkQueueStatus.READY for q in work_queues
        )
        await session.commit()

        await Foreman().run_once()

        assert len(AssertingEventsClient.all) == 0
