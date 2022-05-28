from typing import List
from uuid import uuid4

import pydantic
import pytest
from fastapi import status

from prefect.orion import models, schemas
from prefect.orion.models import block_documents
from prefect.orion.schemas.actions import BlockDocumentCreate
from prefect.orion.schemas.core import BlockDocument


@pytest.fixture
async def block_schemas(session, block_type_x, block_type_y):
    block_schema_0 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={}, block_type_id=block_type_x.id
        ),
    )
    await session.commit()

    block_schema_1 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={"x": {"type": "int"}}, block_type_id=block_type_y.id
        ),
    )
    await session.commit()

    block_schema_2 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={"y": {"type": "int"}}, block_type_id=block_type_x.id
        ),
    )
    await session.commit()

    return block_schema_0, block_schema_1, block_schema_2


class TestCreateBlockDocument:
    async def test_create_block_document(self, session, client, block_schemas):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = BlockDocument.parse_obj(response.json())

        assert result.name == "x"
        assert result.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum

        response = await client.get(f"/block_documents/{result.id}")
        api_block = BlockDocument.parse_obj(response.json())
        assert api_block.name == "x"
        assert api_block.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum

    async def test_create_block_document_already_exists(
        self, session, client, block_schemas
    ):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_create_block_document_with_same_name_but_different_block_type(
        self, session, client, block_schemas
    ):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize(
        "name",
        [
            "my block",
            "my:block",
            r"my\block",
            "my👍block",
            "my|block",
        ],
    )
    async def test_create_block_document_with_nonstandard_characters(
        self, client, name, block_schemas
    ):
        response = await client.post(
            "/block_documents/",
            json=dict(
                name=name,
                data=dict(),
                block_schema_id=str(block_schemas[0].id),
                block_type_id=str(block_schemas[0].block_type_id),
            ),
        )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize(
        "name",
        [
            "my%block",
            "my/block",
        ],
    )
    async def test_create_block_document_with_invalid_characters(
        self, client, name, block_schemas
    ):
        response = await client.post(
            "/block_documents/",
            json=dict(
                name=name,
                data=dict(),
                block_schema_id=str(block_schemas[0].id),
                block_type_id=str(block_schemas[0].block_type_id),
            ),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestReadBlockDocument:
    async def test_read_missing_block_document(self, client):
        response = await client.get(f"/block_documents/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadBlockDocuments:
    @pytest.fixture(autouse=True)
    async def block_documents(self, session, block_schemas):

        block_documents = []
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[0].id,
                    name="Block 1",
                    block_type_id=block_schemas[0].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="Block 2",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="Block 3",
                    block_type_id=block_schemas[2].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="Block 4",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="Block 5",
                    block_type_id=block_schemas[2].block_type_id,
                ),
            )
        )

        session.add_all(block_documents)
        await session.commit()
        return block_documents

    async def test_read_block_documents(self, client, block_documents):
        response = await client.post("/block_documents/filter")
        assert response.status_code == status.HTTP_200_OK
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert {b.id for b in read_block_documents} == {b.id for b in block_documents}
        # sorted by block type name, block document name
        assert [b.id for b in read_block_documents] == [
            block_documents[0].id,
            block_documents[2].id,
            block_documents[4].id,
            block_documents[1].id,
            block_documents[3].id,
        ]

    async def test_read_block_documents_limit_offset(self, client, block_documents):
        # sorted by block type name, block document name
        response = await client.post("/block_documents/filter", json=dict(limit=2))
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[0].id,
            block_documents[2].id,
        ]

        response = await client.post(
            "/block_documents/filter", json=dict(limit=2, offset=2)
        )
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[4].id,
            block_documents[1].id,
        ]

    async def test_read_blocks_type(self, client, block_documents):
        response = await client.post(
            "/block_documents/filter",
        )
        read_blocks = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert [b.id for b in read_blocks] == [
            block_documents[0].id,
            block_documents[2].id,
            block_documents[4].id,
            block_documents[1].id,
            block_documents[3].id,
        ]


class TestDeleteBlock:
    async def test_delete_block(self, session, client, block_schemas):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ).dict(json_compatible=True),
        )
        result = BlockDocument.parse_obj(response.json())

        response = await client.get(f"/block_documents/{result.id}")
        assert response.status_code == status.HTTP_200_OK

        response = await client.delete(f"/block_documents/{result.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/block_documents/{result.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_missing_block(self, session, client, block_schemas):
        response = await client.delete(f"/block_documents/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDefaultStorageBlockDocument:
    @pytest.fixture
    async def storage_block_schema(self, session, block_type_x):
        storage_block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={},
                block_type_id=block_type_x.id,
                capabilities=["storage"],
            ),
        )
        await session.commit()
        return storage_block_schema

    @pytest.fixture
    async def storage_block_document(self, session, storage_block_schema):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="storage",
                data=dict(),
                block_schema_id=storage_block_schema.id,
                block_type_id=storage_block_schema.block_type_id,
            ),
        )
        await session.commit()
        return block

    async def test_set_default_storage_block_document(
        self, client, storage_block_document
    ):

        response = await client.post(
            f"/block_documents/get_default_storage_block_document"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not response.content

        await client.post(
            f"/block_documents/{storage_block_document.id}/set_default_storage_block_document"
        )

        response = await client.post(
            f"/block_documents/get_default_storage_block_document"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == str(storage_block_document.id)

    async def test_set_default_fails_if_not_storage_block_document(
        self, session, client, block_schemas
    ):
        non_storage_block_document = await models.block_documents.create_block_document(
            session=session,
            block_document=BlockDocumentCreate(
                name="non-storage",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )
        await session.commit()

        response = await client.post(
            f"/block_documents/{non_storage_block_document.id}/set_default_storage_block_document"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        response = await client.post(
            f"/block_documents/get_default_storage_block_document"
        )
        assert not response.content

    async def test_get_default_storage_block_document(
        self, client, storage_block_document
    ):
        await client.post(
            f"/block_documents/{storage_block_document.id}/set_default_storage_block_document"
        )

        response = await client.post(
            f"/block_documents/get_default_storage_block_document"
        )
        result = schemas.core.BlockDocument.parse_obj(response.json())
        assert result.id == storage_block_document.id

    async def test_clear_default_storage_block_document(
        self, client, storage_block_document
    ):
        await client.post(
            f"/block_documents/{storage_block_document.id}/set_default_storage_block_document"
        )

        response = await client.post(
            f"/block_documents/get_default_storage_block_document"
        )
        assert response.json()["id"] == str(storage_block_document.id)

        await client.post(f"/block_documents/clear_default_storage_block_document")

        response = await client.post(
            f"/block_documents/get_default_storage_block_document"
        )
        assert not response.content
