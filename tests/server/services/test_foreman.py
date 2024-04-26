from datetime import timedelta
from typing import TYPE_CHECKING

import pendulum
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.statuses import DeploymentStatus
from prefect.server.services.foreman import Foreman

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMDeployment


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

    last_polled = pendulum.now("UTC") - timedelta(60)
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

    last_polled = pendulum.now("UTC")

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
    async def test_status_update_when_deployment_has_old_last_polled_time(
        self,
        session: AsyncSession,
        client: AsyncClient,
    ):
        deployment = await create_deployment_with_old_last_polled_time(session=session)
        assert deployment
        assert deployment.status == "READY"

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

        await Foreman().run_once()

        # Check deployment remains ready
        response = await client.get(f"/deployments/{deployment.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "READY"

        events = [event for item in AssertingEventsClient.all for event in item.events]
        assert len(events) == 0

    async def test_foreman_with_no_deployments_to_update(self):
        """
        Foreman should not retrieve more than the batch size of work pools and
        deployments at a time.
        """

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
            pendulum.now("UTC")
            - timedelta(seconds=Foreman()._deployment_last_polled_timeout_seconds)
        )

        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=deployment.work_queue_id,
            work_queue=schemas.actions.WorkQueueUpdate(last_polled=pendulum.now("UTC")),
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
