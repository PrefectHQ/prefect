from uuid import uuid4

import pytest
from httpx import AsyncClient

from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import BlockTypeCreate

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


async def _create_block_type(client: AsyncClient, name: str, slug: str) -> dict:
    data = BlockTypeCreate(
        name=name,
        slug=slug,
        description="a block type",
    ).model_dump(mode="json")
    response = await client.post("/block_types/", json=data)
    assert response.status_code == 201, response.text
    return response.json()


class TestBlockTypeLifecycleEvents:
    async def test_create_block_type_emits_created_event(self, client: AsyncClient):
        block_type = await _create_block_type(client, "Events Create", "events-create")

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.block-type.created",
            resource={
                "prefect.resource.id": f"prefect.block-type.{block_type['id']}",
                "prefect.resource.name": "Events Create",
            },
            payload={
                "name": "Events Create",
                "slug": "events-create",
                "description": "a block type",
                "is_protected": False,
            },
        )

    async def test_update_block_type_emits_updated_event(self, client: AsyncClient):
        block_type = await _create_block_type(client, "Events Update", "events-update")
        AssertingEventsClient.reset()

        response = await client.patch(
            f"/block_types/{block_type['id']}",
            json={"description": "updated description"},
        )
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.block-type.updated",
            resource={
                "prefect.resource.id": f"prefect.block-type.{block_type['id']}",
                "prefect.resource.name": "Events Update",
            },
            payload={
                "name": "Events Update",
                "slug": "events-update",
                "description": "updated description",
                "is_protected": False,
            },
        )

    async def test_delete_block_type_emits_deleted_event(self, client: AsyncClient):
        block_type = await _create_block_type(client, "Events Delete", "events-delete")
        AssertingEventsClient.reset()

        response = await client.delete(f"/block_types/{block_type['id']}")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.block-type.deleted",
            resource={
                "prefect.resource.id": f"prefect.block-type.{block_type['id']}",
                "prefect.resource.name": "Events Delete",
            },
        )

    async def test_delete_nonexistent_block_type_does_not_emit_event(
        self, client: AsyncClient
    ):
        response = await client.delete(f"/block_types/{uuid4()}")
        assert response.status_code == 404

        AssertingEventsClient.assert_no_emitted_event_with(
            event="prefect.block-type.deleted",
        )
