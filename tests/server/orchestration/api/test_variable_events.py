from uuid import uuid4

import pytest
from httpx import AsyncClient

from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import VariableCreate

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


class TestVariableLifecycleEvents:
    async def test_create_variable_emits_created_event(self, client: AsyncClient):
        data = VariableCreate(
            name="events_create", value="hello", tags=["a", "b"]
        ).model_dump(mode="json")
        response = await client.post("/variables/", json=data)
        assert response.status_code == 201
        variable_id = response.json()["id"]

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.variable.created",
            resource={
                "prefect.resource.id": f"prefect.variable.{variable_id}",
                "prefect.resource.name": "events_create",
            },
            payload={"name": "events_create", "value": "hello", "tags": ["a", "b"]},
        )

    async def test_update_variable_emits_updated_event(self, client: AsyncClient):
        created = await client.post(
            "/variables/",
            json=VariableCreate(name="events_update", value="before").model_dump(
                mode="json"
            ),
        )
        variable_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.patch(
            f"/variables/{variable_id}",
            json={"value": "after"},
        )
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.variable.updated",
            resource={
                "prefect.resource.id": f"prefect.variable.{variable_id}",
                "prefect.resource.name": "events_update",
            },
            payload={"name": "events_update", "value": "after", "tags": []},
        )

    async def test_update_variable_by_name_emits_updated_event_with_post_state(
        self, client: AsyncClient
    ):
        created = await client.post(
            "/variables/",
            json=VariableCreate(name="events_rename", value="v").model_dump(
                mode="json"
            ),
        )
        variable_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.patch(
            "/variables/name/events_rename",
            json={"name": "events_renamed"},
        )
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.variable.updated",
            resource={
                "prefect.resource.id": f"prefect.variable.{variable_id}",
                "prefect.resource.name": "events_renamed",
            },
            payload={"name": "events_renamed", "value": "v", "tags": []},
        )

    async def test_delete_variable_emits_deleted_event(self, client: AsyncClient):
        created = await client.post(
            "/variables/",
            json=VariableCreate(
                name="events_delete", value="bye", tags=["x"]
            ).model_dump(mode="json"),
        )
        variable_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.delete(f"/variables/{variable_id}")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.variable.deleted",
            resource={
                "prefect.resource.id": f"prefect.variable.{variable_id}",
                "prefect.resource.name": "events_delete",
            },
            payload={"name": "events_delete", "value": "bye", "tags": ["x"]},
        )

    async def test_delete_variable_by_name_emits_deleted_event(
        self, client: AsyncClient
    ):
        created = await client.post(
            "/variables/",
            json=VariableCreate(name="events_delete_by_name", value="bye").model_dump(
                mode="json"
            ),
        )
        variable_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.delete("/variables/name/events_delete_by_name")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.variable.deleted",
            resource={
                "prefect.resource.id": f"prefect.variable.{variable_id}",
                "prefect.resource.name": "events_delete_by_name",
            },
        )

    async def test_update_nonexistent_variable_does_not_emit_event(
        self, client: AsyncClient
    ):
        response = await client.patch(
            f"/variables/{uuid4()}",
            json={"value": "nope"},
        )
        assert response.status_code == 404

        AssertingEventsClient.assert_no_emitted_event_with(
            event="prefect.variable.updated",
        )

    async def test_delete_nonexistent_variable_does_not_emit_event(
        self, client: AsyncClient
    ):
        response = await client.delete(f"/variables/{uuid4()}")
        assert response.status_code == 404

        AssertingEventsClient.assert_no_emitted_event_with(
            event="prefect.variable.deleted",
        )
