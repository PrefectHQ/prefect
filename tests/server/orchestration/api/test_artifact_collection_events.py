import pytest
from httpx import AsyncClient

from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import ArtifactCreate

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


async def _create_artifact(client: AsyncClient, key: str, data: str) -> dict:
    response = await client.post(
        "/artifacts/",
        json=ArtifactCreate(
            key=key,
            type="markdown",
            data=data,
            description="a description",
        ).model_dump(mode="json"),
    )
    assert response.status_code == 201, response.text
    return response.json()


class TestArtifactCollectionLifecycleEvents:
    async def test_first_keyed_artifact_emits_collection_created_event(
        self, client: AsyncClient
    ):
        artifact = await _create_artifact(client, "events-collection", "# hello")

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.artifact-collection.created",
            related=[
                {
                    "prefect.resource.id": f"prefect.artifact.{artifact['id']}",
                    "prefect.resource.role": "latest",
                }
            ],
            payload={
                "key": "events-collection",
                "type": "markdown",
                "data": "# hello",
                "description": "a description",
            },
        )

    async def test_second_keyed_artifact_emits_collection_updated_event(
        self, client: AsyncClient
    ):
        await _create_artifact(client, "events-collection-update", "v1")
        AssertingEventsClient.reset()

        second = await _create_artifact(client, "events-collection-update", "v2")

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.artifact-collection.updated",
            related=[
                {
                    "prefect.resource.id": f"prefect.artifact.{second['id']}",
                    "prefect.resource.role": "latest",
                }
            ],
            payload={
                "key": "events-collection-update",
                "type": "markdown",
                "data": "v2",
                "description": "a description",
            },
        )

    async def test_delete_latest_with_prior_emits_collection_updated_event(
        self, client: AsyncClient
    ):
        first = await _create_artifact(client, "events-collection-repoint", "v1")
        second = await _create_artifact(client, "events-collection-repoint", "v2")
        AssertingEventsClient.reset()

        response = await client.delete(f"/artifacts/{second['id']}")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.artifact-collection.updated",
            related=[
                {
                    "prefect.resource.id": f"prefect.artifact.{first['id']}",
                    "prefect.resource.role": "latest",
                }
            ],
            payload={
                "key": "events-collection-repoint",
                "type": "markdown",
                "data": "v1",
                "description": "a description",
            },
        )

    async def test_delete_last_artifact_emits_collection_deleted_event(
        self, client: AsyncClient
    ):
        only = await _create_artifact(client, "events-collection-delete", "v1")
        AssertingEventsClient.reset()

        response = await client.delete(f"/artifacts/{only['id']}")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.artifact-collection.deleted",
            related=[
                {
                    "prefect.resource.id": f"prefect.artifact.{only['id']}",
                    "prefect.resource.role": "latest",
                }
            ],
            payload={
                "key": "events-collection-delete",
                "type": "markdown",
            },
        )
