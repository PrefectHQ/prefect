import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import WorkPoolCreate, WorkQueueCreate

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


class TestWorkPoolLifecycleEvents:
    async def test_create_work_pool_emits_created_event(self, client: AsyncClient):
        response = await client.post(
            "/work_pools/",
            json=WorkPoolCreate(name="events-pool", type="test").model_dump(
                mode="json"
            ),
        )
        assert response.status_code == 201, response.text
        pool = response.json()

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-pool.created",
            resource={
                "prefect.resource.id": f"prefect.work-pool.{pool['id']}",
                "prefect.resource.name": "events-pool",
            },
            related=[
                {
                    "prefect.resource.id": (
                        f"prefect.work-queue.{pool['default_queue_id']}"
                    ),
                    "prefect.resource.role": "default-queue",
                }
            ],
        )

    async def test_delete_work_pool_emits_deleted_event(self, client: AsyncClient):
        created = await client.post(
            "/work_pools/",
            json=WorkPoolCreate(name="events-pool-delete", type="test").model_dump(
                mode="json"
            ),
        )
        pool = created.json()
        AssertingEventsClient.reset()

        response = await client.delete("/work_pools/events-pool-delete")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-pool.deleted",
            resource={
                "prefect.resource.id": f"prefect.work-pool.{pool['id']}",
                "prefect.resource.name": "events-pool-delete",
            },
        )


class TestWorkQueueLifecycleEvents:
    async def test_create_work_queue_emits_created_event(
        self, session: AsyncSession, work_pool
    ):
        AssertingEventsClient.reset()
        queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=WorkQueueCreate(name="events-queue"),
        )
        await session.commit()

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.created",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{queue.id}",
                "prefect.resource.name": "events-queue",
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool.id}",
                    "prefect.resource.role": "work-pool",
                }
            ],
        )

    async def test_delete_work_queue_emits_deleted_event(
        self, session: AsyncSession, work_pool
    ):
        queue = await models.workers.create_work_queue(
            session=session,
            work_pool_id=work_pool.id,
            work_queue=WorkQueueCreate(name="events-queue-delete"),
        )
        await session.commit()
        AssertingEventsClient.reset()

        deleted = await models.workers.delete_work_queue(
            session=session, work_queue_id=queue.id
        )
        await session.commit()
        assert deleted is True

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.work-queue.deleted",
            resource={
                "prefect.resource.id": f"prefect.work-queue.{queue.id}",
                "prefect.resource.name": "events-queue-delete",
            },
        )


class TestDeploymentRelatedResources:
    async def test_deployment_updated_event_includes_storage_related(
        self, client: AsyncClient, deployment
    ):
        # The `deployment` fixture is created with a storage block document.
        assert deployment.storage_document_id is not None
        AssertingEventsClient.reset()

        response = await client.patch(
            f"/deployments/{deployment.id}",
            json={"description": "touch to emit an update"},
        )
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.deployment.updated",
            resource={
                "prefect.resource.id": f"prefect.deployment.{deployment.id}",
            },
            related=[
                {
                    "prefect.resource.id": (
                        f"prefect.block-document.{deployment.storage_document_id}"
                    ),
                    "prefect.resource.role": "storage",
                }
            ],
        )
