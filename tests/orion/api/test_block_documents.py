from typing import List
from uuid import uuid4

import pydantic
import pytest
from fastapi import status

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockDocumentCreate, BlockDocumentUpdate
from prefect.orion.schemas.core import BlockDocument


@pytest.fixture
async def block_schemas(session, block_type_x, block_type_y):
    class A(Block):
        _block_schema_type = "abc"

    block_type_a = await models.block_types.create_block_type(
        session=session, block_type=A._to_block_type()
    )
    block_schema_a = await models.block_schemas.create_block_schema(
        session=session, block_schema=A._to_block_schema(block_type_id=block_type_a.id)
    )

    class B(Block):
        _block_schema_type = "abc"

        x: int

    block_type_b = await models.block_types.create_block_type(
        session=session, block_type=B._to_block_type()
    )
    block_schema_b = await models.block_schemas.create_block_schema(
        session=session, block_schema=B._to_block_schema(block_type_id=block_type_b.id)
    )

    class C(Block):
        y: int

    block_type_c = await models.block_types.create_block_type(
        session=session, block_type=C._to_block_type()
    )
    block_schema_c = await models.block_schemas.create_block_schema(
        session=session, block_schema=C._to_block_schema(block_type_id=block_type_c.id)
    )

    class D(Block):
        b: B
        z: str

    block_type_d = await models.block_types.create_block_type(
        session=session, block_type=D._to_block_type()
    )
    block_schema_d = await models.block_schemas.create_block_schema(
        session=session, block_schema=D._to_block_schema(block_type_id=block_type_d.id)
    )

    class E(Block):
        c: C
        d: D

    block_type_e = await models.block_types.create_block_type(
        session=session, block_type=E._to_block_type()
    )
    block_schema_e = await models.block_schemas.create_block_schema(
        session=session, block_schema=E._to_block_schema(block_type_id=block_type_e.id)
    )

    await session.commit()

    return (
        block_schema_a,
        block_schema_b,
        block_schema_c,
        block_schema_d,
        block_schema_e,
    )


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
        assert result.is_anonymous is False

        response = await client.get(f"/block_documents/{result.id}")
        api_block = BlockDocument.parse_obj(response.json())
        assert api_block.name == "x"
        assert api_block.data == dict(y=1)
        assert api_block.is_anonymous is False
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum

    async def test_create_anonymous_block_document(
        self, session, client, block_schemas
    ):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = BlockDocument.parse_obj(response.json())

        assert result.name.startswith("anonymous:")
        assert result.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum
        assert result.is_anonymous is True

        response = await client.get(f"/block_documents/{result.id}")
        api_block = BlockDocument.parse_obj(response.json())
        assert api_block.name.startswith("anonymous:")
        assert api_block.data == dict(y=1)
        assert api_block.is_anonymous is True
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

    async def test_create_anonymous_block_document_already_exists(
        self, session, client, block_schemas
    ):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_200_OK

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

    async def test_create_anonymous_block_document_with_same_name_but_different_block_type(
        self, session, client, block_schemas
    ):
        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
                is_anonymous=True,
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
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    block_type_id=block_schemas[2].block_type_id,
                    is_anonymous=True,
                ),
            )
        )

        await session.commit()
        return sorted(block_documents, key=lambda b: b.name)

    async def test_read_block_documents(self, client, block_documents):
        response = await client.post("/block_documents/filter")
        assert response.status_code == status.HTTP_200_OK
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        # sorted by block type name, block document name
        # anonymous blocks excluded by default
        assert [b.id for b in read_block_documents] == [
            b.id for b in block_documents if not b.is_anonymous
        ]

        # make sure that API results are as expected
        required_attrs = [
            "id",
            "created",
            "updated",
            "name",
            "data",
            "block_schema_id",
            "block_schema",
            "block_type_id",
            "block_type",
            "block_document_references",
        ]

        for b in read_block_documents:
            for attr in required_attrs:
                assert getattr(b, attr) is not None

    @pytest.mark.parametrize("is_anonymous", [True, False])
    async def test_read_block_documents_with_filter_is_anonymous(
        self, client, block_documents, is_anonymous
    ):
        response = await client.post(
            "/block_documents/filter",
            json=dict(block_document_filter=dict(is_anonymous=dict(eq_=is_anonymous))),
        )
        assert response.status_code == status.HTTP_200_OK
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        # sorted by block type name, block document name
        assert [b.id for b in read_block_documents] == [
            b.id for b in block_documents if b.is_anonymous is is_anonymous
        ]

    @pytest.mark.parametrize("is_anonymous_filter", [None, dict(eq_=None)])
    async def test_read_block_documents_with_both_anonymous_and_non_anonymous(
        self, client, block_documents, is_anonymous_filter
    ):
        """
        anonymous blocks are filtered by default, so have to explicitly disable
        the filter to get all blocks. This can be done either by disabling the
        is_anonymous filter (recommended) OR by setting eq_=None and we test
        both to make sure the default value doesn't override
        """
        response = await client.post(
            "/block_documents/filter",
            json=dict(block_document_filter=dict(is_anonymous=is_anonymous_filter)),
        )
        assert response.status_code == status.HTTP_200_OK
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        # sorted by block type name, block document name
        assert [b.id for b in read_block_documents] == [b.id for b in block_documents]

    async def test_read_block_documents_limit_offset(self, client, block_documents):
        # sorted by block type name, block document name
        response = await client.post("/block_documents/filter", json=dict(limit=2))
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[0].id,
            block_documents[1].id,
        ]

        response = await client.post(
            "/block_documents/filter", json=dict(limit=2, offset=2)
        )
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[2].id,
            block_documents[3].id,
        ]


class TestDeleteBlockDocument:
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


class TestUpdateBlockDocument:
    async def test_update_block_document_name(self, session, client, block_schemas):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-name",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )
        await session.commit()

        response = await client.patch(
            f"/block_documents/{block_document.id}",
            json=BlockDocumentUpdate(
                name="updated",
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.name == "updated"

    async def test_update_block_document_data(self, session, client, block_schemas):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-data",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await session.commit()

        response = await client.patch(
            f"/block_documents/{block_document.id}",
            json=BlockDocumentUpdate(
                data=dict(x=2),
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.data == dict(x=2)

    async def test_update_anonymous_block_document_data(
        self, session, client, block_schemas
    ):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
                is_anonymous=True,
            ),
        )

        await session.commit()

        response = await client.patch(
            f"/block_documents/{block_document.id}",
            json=BlockDocumentUpdate(
                data=dict(x=2),
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.data == dict(x=2)

    async def test_update_nested_block_document_data(
        self, session, client, block_schemas
    ):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        await session.commit()

        block_document_before_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_before_update.data == {
            "b": {"x": 1},
            "z": "zzzzz",
        }
        assert block_document_before_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "block_document_references": {},
                }
            }
        }

        response = await client.patch(
            f"/block_documents/{inner_block_document.id}",
            json=BlockDocumentUpdate(
                data=dict(x=4),
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        block_document_after_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_after_update.data == {
            "b": {"x": 4},
            "z": "zzzzz",
        }
        assert block_document_after_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "block_document_references": {},
                }
            }
        }

    async def test_update_nested_block_document_reference(
        self, session, client, block_schemas
    ):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        await session.commit()

        block_document_before_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_before_update.data == {
            "b": {"x": 1},
            "z": "zzzzz",
        }
        assert block_document_before_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": inner_block_document.id,
                    "name": inner_block_document.name,
                    "block_type": inner_block_document.block_type,
                    "block_document_references": {},
                }
            }
        }

        new_inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="this-is-a-new-inner-block",
                data=dict(x=1000),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await session.commit()

        response = await client.patch(
            f"/block_documents/{outer_block_document.id}",
            json=BlockDocumentUpdate(
                data={
                    "b": {"$ref": {"block_document_id": new_inner_block_document.id}},
                    "z": "zzzzz",
                },
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        block_document_after_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_after_update.data == {
            "b": {
                "x": 1000,
            },
            "z": "zzzzz",
        }
        assert block_document_after_update.block_document_references == {
            "b": {
                "block_document": {
                    "id": new_inner_block_document.id,
                    "name": new_inner_block_document.name,
                    "block_type": new_inner_block_document.block_type,
                    "block_document_references": {},
                }
            }
        }

    async def test_update_with_faulty_block_document_reference(
        self, session, client, block_schemas
    ):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        await session.commit()

        response = await client.patch(
            f"/block_documents/{outer_block_document.id}",
            json=BlockDocumentUpdate(
                data={
                    "b": {"$ref": {"block_document_id": uuid4()}},
                    "z": "zzzzz",
                },
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    async def test_update_with_missing_block_document_reference_id(
        self, session, client, block_schemas
    ):
        inner_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data=dict(x=1),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        outer_block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-nested-block",
                data={
                    "b": {"$ref": {"block_document_id": inner_block_document.id}},
                    "z": "zzzzz",
                },
                block_schema_id=block_schemas[3].id,
                block_type_id=block_schemas[3].block_type_id,
            ),
        )

        await session.commit()

        response = await client.patch(
            f"/block_documents/{outer_block_document.id}",
            json=BlockDocumentUpdate(
                data={
                    "b": {"$ref": {}},
                    "z": "zzzzz",
                },
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
