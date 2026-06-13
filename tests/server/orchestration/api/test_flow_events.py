from uuid import uuid4

import pytest
from httpx import AsyncClient

from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import FlowCreate

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


class TestFlowLifecycleEvents:
    async def test_create_flow_emits_created_event(self, client: AsyncClient):
        data = FlowCreate(name="events-flow-create", tags=["a", "b"]).model_dump(
            mode="json"
        )
        response = await client.post("/flows/", json=data)
        assert response.status_code == 201
        flow_id = response.json()["id"]

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.flow.created",
            resource={
                "prefect.resource.id": f"prefect.flow.{flow_id}",
                "prefect.resource.name": "events-flow-create",
            },
            payload={"name": "events-flow-create", "tags": ["a", "b"], "labels": {}},
        )

    async def test_create_existing_flow_does_not_emit_created_event(
        self, client: AsyncClient
    ):
        data = FlowCreate(name="events-flow-idempotent").model_dump(mode="json")
        first = await client.post("/flows/", json=data)
        assert first.status_code == 201
        AssertingEventsClient.reset()

        second = await client.post("/flows/", json=data)
        assert second.status_code == 200

        AssertingEventsClient.assert_no_emitted_event_with(
            event="prefect.flow.created",
        )

    async def test_update_flow_emits_updated_event(self, client: AsyncClient):
        created = await client.post(
            "/flows/",
            json=FlowCreate(name="events-flow-update").model_dump(mode="json"),
        )
        flow_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.patch(
            f"/flows/{flow_id}",
            json={"tags": ["updated"]},
        )
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.flow.updated",
            resource={
                "prefect.resource.id": f"prefect.flow.{flow_id}",
                "prefect.resource.name": "events-flow-update",
            },
            payload={
                "name": "events-flow-update",
                "tags": ["updated"],
                "labels": {},
            },
        )

    async def test_delete_flow_emits_deleted_event(self, client: AsyncClient):
        created = await client.post(
            "/flows/",
            json=FlowCreate(name="events-flow-delete").model_dump(mode="json"),
        )
        flow_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.delete(f"/flows/{flow_id}")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.flow.deleted",
            resource={
                "prefect.resource.id": f"prefect.flow.{flow_id}",
                "prefect.resource.name": "events-flow-delete",
            },
        )

    async def test_bulk_delete_flows_emits_deleted_events(self, client: AsyncClient):
        f1 = await client.post(
            "/flows/", json=FlowCreate(name="bulk-flow-1").model_dump(mode="json")
        )
        f2 = await client.post(
            "/flows/", json=FlowCreate(name="bulk-flow-2").model_dump(mode="json")
        )
        f1_id = f1.json()["id"]
        f2_id = f2.json()["id"]
        AssertingEventsClient.reset()

        response = await client.post(
            "/flows/bulk_delete",
            json={"flows": {"id": {"any_": [f1_id, f2_id]}}},
        )
        assert response.status_code == 200

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.flow.deleted",
            resource={
                "prefect.resource.id": f"prefect.flow.{f1_id}",
                "prefect.resource.name": "bulk-flow-1",
            },
        )
        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.flow.deleted",
            resource={
                "prefect.resource.id": f"prefect.flow.{f2_id}",
                "prefect.resource.name": "bulk-flow-2",
            },
        )

    async def test_update_nonexistent_flow_does_not_emit_event(
        self, client: AsyncClient
    ):
        response = await client.patch(f"/flows/{uuid4()}", json={"tags": ["x"]})
        assert response.status_code == 404

        AssertingEventsClient.assert_no_emitted_event_with(event="prefect.flow.updated")

    async def test_delete_nonexistent_flow_does_not_emit_event(
        self, client: AsyncClient
    ):
        response = await client.delete(f"/flows/{uuid4()}")
        assert response.status_code == 404

        AssertingEventsClient.assert_no_emitted_event_with(event="prefect.flow.deleted")
