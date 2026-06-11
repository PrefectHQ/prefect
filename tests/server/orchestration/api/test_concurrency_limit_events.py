import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import ConcurrencyLimitV2Create

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


class TestConcurrencyLimitV2LifecycleEvents:
    async def test_create_emits_created_event(self, client: AsyncClient):
        response = await client.post(
            "/v2/concurrency_limits/",
            json=ConcurrencyLimitV2Create(name="gcl-create", limit=7).model_dump(
                mode="json"
            ),
        )
        assert response.status_code == 201, response.text
        limit_id = response.json()["id"]

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.concurrency-limit.created",
            resource={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit_id}",
                "prefect.resource.name": "gcl-create",
            },
            payload={
                "name": "gcl-create",
                "limit": 7,
                "active": True,
                "slot_decay_per_second": 0.0,
            },
        )

    async def test_update_emits_updated_event(self, client: AsyncClient):
        created = await client.post(
            "/v2/concurrency_limits/",
            json=ConcurrencyLimitV2Create(name="gcl-update", limit=1).model_dump(
                mode="json"
            ),
        )
        limit_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.patch(
            f"/v2/concurrency_limits/{limit_id}",
            json={"limit": 9},
        )
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.concurrency-limit.updated",
            resource={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit_id}",
                "prefect.resource.name": "gcl-update",
            },
            payload={
                "name": "gcl-update",
                "limit": 9,
                "active": True,
                "slot_decay_per_second": 0.0,
            },
        )

    async def test_delete_emits_deleted_event(self, client: AsyncClient):
        created = await client.post(
            "/v2/concurrency_limits/",
            json=ConcurrencyLimitV2Create(name="gcl-delete", limit=1).model_dump(
                mode="json"
            ),
        )
        limit_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.delete(f"/v2/concurrency_limits/{limit_id}")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.concurrency-limit.deleted",
            resource={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit_id}",
                "prefect.resource.name": "gcl-delete",
            },
        )


class TestConcurrencyLimitV1LifecycleEvents:
    """The v1 REST API is a compatibility shim that creates v2 limits; the v1
    model functions are the legacy/fallback path, exercised here directly."""

    async def test_create_emits_created_event(self, session: AsyncSession):
        limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="v1-create", concurrency_limit=5
            ),
        )
        await session.commit()

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.concurrency-limit.created",
            resource={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit.id}",
                "prefect.resource.name": "v1-create",
            },
            payload={"tag": "v1-create", "concurrency_limit": 5},
        )

    async def test_upsert_existing_emits_updated_event(self, session: AsyncSession):
        await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="v1-upsert", concurrency_limit=5
            ),
        )
        await session.commit()
        AssertingEventsClient.reset()

        limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="v1-upsert", concurrency_limit=8
            ),
        )
        await session.commit()

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.concurrency-limit.updated",
            resource={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit.id}",
                "prefect.resource.name": "v1-upsert",
            },
            payload={"tag": "v1-upsert", "concurrency_limit": 8},
        )

    async def test_delete_by_id_emits_deleted_event(self, session: AsyncSession):
        limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="v1-delete", concurrency_limit=1
            ),
        )
        await session.commit()
        AssertingEventsClient.reset()

        deleted = await models.concurrency_limits.delete_concurrency_limit(
            session=session, concurrency_limit_id=limit.id
        )
        await session.commit()
        assert deleted is True

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.concurrency-limit.deleted",
            resource={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit.id}",
                "prefect.resource.name": "v1-delete",
            },
        )

    async def test_delete_by_tag_emits_deleted_event(self, session: AsyncSession):
        limit = await models.concurrency_limits.create_concurrency_limit(
            session=session,
            concurrency_limit=schemas.core.ConcurrencyLimit(
                tag="v1-delete-by-tag", concurrency_limit=1
            ),
        )
        await session.commit()
        AssertingEventsClient.reset()

        deleted = await models.concurrency_limits.delete_concurrency_limit_by_tag(
            session=session, tag="v1-delete-by-tag"
        )
        await session.commit()
        assert deleted is True

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.concurrency-limit.deleted",
            resource={
                "prefect.resource.id": f"prefect.concurrency-limit.{limit.id}",
                "prefect.resource.name": "v1-delete-by-tag",
            },
        )
