import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.schemas.actions import (
    BlockDocumentCreate,
    BlockSchemaCreate,
    BlockTypeCreate,
)

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def reset_events():
    AssertingEventsClient.reset()


class TestBlockDocumentLifecycleEvents:
    async def test_create_block_document_emits_created_event(
        self, client: AsyncClient, block_schema, block_type_x
    ):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="events-block",
                data={"foo": "bar"},
                block_schema_id=block_schema.id,
                block_type_id=block_type_x.id,
            ).model_dump(mode="json"),
        )
        assert response.status_code == 201, response.text
        block_document_id = response.json()["id"]

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.block-document.created",
            resource={
                "prefect.resource.id": (f"prefect.block-document.{block_document_id}"),
                "prefect.resource.name": "events-block",
            },
            related=[
                {
                    "prefect.resource.id": f"prefect.block-type.{block_type_x.id}",
                    "prefect.resource.name": block_type_x.name,
                    "prefect.resource.role": "block-type",
                },
                {
                    "prefect.resource.id": f"prefect.block-schema.{block_schema.id}",
                    "prefect.resource.role": "block-schema",
                },
            ],
            payload={
                "name": "events-block",
                "data": {"foo": "bar"},
                "block_schema": {
                    "capabilities": [],
                    "block_type": {
                        "id": str(block_type_x.id),
                        "name": block_type_x.name,
                    },
                },
            },
        )

    async def test_update_block_document_emits_updated_event(
        self, client: AsyncClient, block_schema, block_type_x
    ):
        created = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="events-block-update",
                data={"foo": "before"},
                block_schema_id=block_schema.id,
                block_type_id=block_type_x.id,
            ).model_dump(mode="json"),
        )
        block_document_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.patch(
            f"/block_documents/{block_document_id}",
            json={"data": {"foo": "after"}, "merge_existing_data": False},
        )
        assert response.status_code == 204, response.text

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.block-document.updated",
            resource={
                "prefect.resource.id": (f"prefect.block-document.{block_document_id}"),
                "prefect.resource.name": "events-block-update",
            },
            payload={
                "name": "events-block-update",
                "data": {"foo": "after"},
                "block_schema": {
                    "capabilities": [],
                    "block_type": {
                        "id": str(block_type_x.id),
                        "name": block_type_x.name,
                    },
                },
            },
        )

    async def test_delete_block_document_emits_deleted_event(
        self, client: AsyncClient, block_schema, block_type_x
    ):
        created = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="events-block-delete",
                data={"foo": "bar"},
                block_schema_id=block_schema.id,
                block_type_id=block_type_x.id,
            ).model_dump(mode="json"),
        )
        block_document_id = created.json()["id"]
        AssertingEventsClient.reset()

        response = await client.delete(f"/block_documents/{block_document_id}")
        assert response.status_code == 204

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.block-document.deleted",
            resource={
                "prefect.resource.id": (f"prefect.block-document.{block_document_id}"),
                "prefect.resource.name": "events-block-delete",
            },
        )

    async def test_created_event_excludes_secret_field_values(
        self, client: AsyncClient, session: AsyncSession
    ):
        block_type = await models.block_types.create_block_type(
            session=session,
            block_type=BlockTypeCreate(name="secretish", slug="secretish"),
        )
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=BlockSchemaCreate(
                fields={
                    "title": "secretish",
                    "type": "object",
                    "properties": {
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                    },
                    "secret_fields": ["password"],
                    "block_schema_references": {},
                },
                block_type_id=block_type.id,
            ),
        )
        await session.commit()
        AssertingEventsClient.reset()

        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="has-secret",
                data={"username": "alice", "password": "hunter2"},
                block_schema_id=block_schema.id,
                block_type_id=block_type.id,
            ).model_dump(mode="json"),
        )
        assert response.status_code == 201, response.text
        block_document_id = response.json()["id"]

        AssertingEventsClient.assert_emitted_event_with(
            event="prefect.block-document.created",
            resource={
                "prefect.resource.id": (f"prefect.block-document.{block_document_id}"),
                "prefect.resource.name": "has-secret",
            },
            payload={
                "name": "has-secret",
                "data": {"username": "alice"},
            },
        )

    async def test_anonymous_block_document_does_not_emit_event(
        self, session: AsyncSession, block_schema, block_type_x
    ):
        AssertingEventsClient.reset()
        await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                data={"foo": "bar"},
                block_schema_id=block_schema.id,
                block_type_id=block_type_x.id,
                is_anonymous=True,
            ),
        )
        await session.commit()

        AssertingEventsClient.assert_no_emitted_event_with(
            event="prefect.block-document.created",
        )
