import string
from typing import List
from uuid import uuid4

import pydantic
import pytest
from fastapi import status
from pydantic import SecretBytes, SecretStr

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockDocumentCreate, BlockDocumentUpdate
from prefect.orion.schemas.core import BlockDocument
from prefect.utilities.names import obfuscate_string


def long_string(s: str):
    return string.ascii_letters + s


X = long_string("x")
Y = long_string("y")
Z = long_string("z")


@pytest.fixture
async def block_schemas(session, block_type_x, block_type_y):
    class CanRun(Block):
        _block_schema_capabilities = ["run"]

        def run(self):
            pass

    class CanFly(Block):
        _block_schema_capabilities = ["fly"]

        def fly(self):
            pass

    class CanSwim(Block):
        _block_schema_capabilities = ["swim"]

        def swim(self):
            pass

    class A(Block):
        pass

    block_type_a = await models.block_types.create_block_type(
        session=session, block_type=A._to_block_type()
    )
    block_schema_a = await models.block_schemas.create_block_schema(
        session=session, block_schema=A._to_block_schema(block_type_id=block_type_a.id)
    )

    class B(CanFly, Block):

        x: int

    block_type_b = await models.block_types.create_block_type(
        session=session, block_type=B._to_block_type()
    )
    block_schema_b = await models.block_schemas.create_block_schema(
        session=session, block_schema=B._to_block_schema(block_type_id=block_type_b.id)
    )

    class C(CanRun, Block):
        y: int

    block_type_c = await models.block_types.create_block_type(
        session=session, block_type=C._to_block_type()
    )
    block_schema_c = await models.block_schemas.create_block_schema(
        session=session, block_schema=C._to_block_schema(block_type_id=block_type_c.id)
    )

    class D(CanSwim, CanFly, Block):
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

        assert result.name.startswith("anonymous-")
        assert result.data == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum
        assert result.is_anonymous is True

        response = await client.get(f"/block_documents/{result.id}")
        api_block = BlockDocument.parse_obj(response.json())
        assert api_block.name.startswith("anonymous-")
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

    async def test_create_multiple_anonymous_block_document_without_names(
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

        response2 = await client.post(
            "/block_documents/",
            json=BlockDocumentCreate(
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
                is_anonymous=True,
            ).dict(json_compatible=True),
        )
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.json()["name"] != response.json()["name"]

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
            "my-block",
            "myblock",
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
            "my block",
            r"my\block",
            "my👍block",
            "my|block",
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

    async def test_read_nonsense_block_document(self, client):
        """Regression test for an issue we observed in Cloud where a client made
        requests for /block_documents/null"""
        response = await client.get(f"/block_documents/not-even")
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
                    name="block-1",
                    block_type_id=block_schemas[0].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="block-2",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="block-3",
                    block_type_id=block_schemas[2].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="block-4",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="block-5",
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

        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    name="nested-block-1",
                    block_schema_id=block_schemas[3].id,
                    block_type_id=block_schemas[3].block_type_id,
                    data={
                        "b": {"$ref": {"block_document_id": block_documents[1].id}},
                        "z": "index",
                    },
                ),
            )
        )

        block_documents.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    name="nested-block-2",
                    block_schema_id=block_schemas[4].id,
                    block_type_id=block_schemas[4].block_type_id,
                    data={
                        "c": {"$ref": {"block_document_id": block_documents[2].id}},
                        "d": {"$ref": {"block_document_id": block_documents[5].id}},
                    },
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
        # sorted by block document name
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

    async def test_read_nonsense_block_document(self, client, block_documents):
        """Regression test for an issue we observed in Cloud where a client made
        requests for /block_documents/null"""
        response = await client.get(f"/block_documents/not-even")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize("is_anonymous", [True, False])
    async def test_read_block_documents_with_filter_is_anonymous(
        self, client, block_documents, is_anonymous
    ):
        response = await client.post(
            "/block_documents/filter",
            json=dict(block_documents=dict(is_anonymous=dict(eq_=is_anonymous))),
        )
        assert response.status_code == status.HTTP_200_OK
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        # sorted by block document name
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
            json=dict(block_documents=dict(is_anonymous=is_anonymous_filter)),
        )
        assert response.status_code == status.HTTP_200_OK
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        # sorted by block document name
        assert [b.id for b in read_block_documents] == [b.id for b in block_documents]

    async def test_read_block_documents_limit_offset(self, client, block_documents):
        # sorted by block document name
        response = await client.post("/block_documents/filter", json=dict(limit=2))
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[1].id,
            block_documents[2].id,
        ]

        response = await client.post(
            "/block_documents/filter", json=dict(limit=2, offset=2)
        )
        read_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert [b.id for b in read_block_documents] == [
            block_documents[3].id,
            block_documents[4].id,
        ]

    async def test_read_block_documents_filter_capabilities(
        self, client, block_documents
    ):
        response = await client.post(
            "/block_documents/filter",
            json=dict(
                block_schemas=dict(block_capabilities=dict(all_=["fly", "swim"]))
            ),
        )
        assert response.status_code == 200
        fly_and_swim_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )

        assert len(fly_and_swim_block_documents) == 1
        assert fly_and_swim_block_documents[0].id == block_documents[6].id

        response = await client.post(
            "/block_documents/filter",
            json=dict(block_schemas=dict(block_capabilities=dict(all_=["fly"]))),
        )
        assert response.status_code == 200
        fly_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert len(fly_block_documents) == 3
        assert [b.id for b in fly_block_documents] == [
            block_documents[2].id,
            block_documents[4].id,
            block_documents[6].id,
        ]

        response = await client.post(
            "/block_documents/filter",
            json=dict(block_schemas=dict(block_capabilities=dict(all_=["swim"]))),
        )
        assert response.status_code == 200
        swim_block_documents = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )
        assert len(swim_block_documents) == 1
        assert swim_block_documents[0].id == block_documents[6].id

    async def test_read_block_documents_filter_types(self, client, block_documents):
        response = await client.post(
            "/block_documents/filter",
            json=dict(block_types=dict(slug=dict(any_=["a", "b"]))),
        )
        assert response.status_code == 200
        docs = pydantic.parse_obj_as(List[schemas.core.BlockDocument], response.json())
        assert len(docs) == 3
        assert len([d for d in docs if d.block_type.slug == "a"]) == 1
        assert len([d for d in docs if d.block_type.slug == "b"]) == 2
        assert [b.id for b in docs] == [
            block_documents[1].id,
            block_documents[2].id,
            block_documents[4].id,
        ]

    async def test_read_block_documents_filter_multiple(self, client, block_documents):
        response = await client.post(
            "/block_documents/filter",
            json=dict(
                block_types=dict(slug=dict(any_=["a", "b"])),
                block_schemas=dict(block_capabilities=dict(all_=["fly"])),
            ),
        )
        assert response.status_code == 200
        docs = pydantic.parse_obj_as(List[schemas.core.BlockDocument], response.json())
        assert [b.id for b in docs] == [block_documents[2].id, block_documents[4].id]


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

    async def test_delete_nonsense_block_document(self, client, block_schemas):
        """Regression test for an issue we observed in Cloud where a client made
        requests for /block_documents/null"""
        response = await client.get("/block_documents/not-even")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateBlockDocument:
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

    @pytest.mark.parametrize("new_data", [{"x": 4}, {}])
    async def test_update_block_document_data_without_merging_existing_data(
        self, session, client, block_schemas, new_data
    ):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-data",
                data=dict(x=1, y=2, z=3),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await session.commit()

        response = await client.patch(
            f"/block_documents/{block_document.id}",
            json=BlockDocumentUpdate(
                data=new_data,
                merge_existing_data=False,
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.data == new_data

    async def test_partial_update_block_document_data(
        self, session, client, block_schemas
    ):
        block_document = await models.block_documents.create_block_document(
            session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="test-update-data",
                data=dict(x=1, y=2, z=3),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )

        await session.commit()

        response = await client.patch(
            f"/block_documents/{block_document.id}",
            json=BlockDocumentUpdate(
                data=dict(y=99),
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        updated_block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id=block_document.id
        )
        assert updated_block_document.data == dict(x=1, y=99, z=3)

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
                    "is_anonymous": False,
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
                    "is_anonymous": False,
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
                    "is_anonymous": False,
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
                    "is_anonymous": False,
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

    async def test_update_nonsense_block_document(self, client):
        """Regression test for an issue we observed in Cloud where a client made
        requests for /block_documents/null"""
        response = await client.patch(
            "/block_documents/not-even",
            json=BlockDocumentUpdate(
                data={
                    "b": {"$ref": {}},
                    "z": "zzzzz",
                },
            ).dict(json_compatible=True, exclude_unset=True),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_nested_block_document_reference_through_removing(
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
                    "is_anonymous": False,
                    "block_document_references": {},
                }
            }
        }

        response = await client.patch(
            f"/block_documents/{outer_block_document.id}",
            json=BlockDocumentUpdate(
                data={
                    "b": {},  # removes block document refs
                    "z": "zzzzz",
                },
                merge_existing_data=False,
            ).dict(json_compatible=True, exclude_unset=True),
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        block_document_after_update = (
            await models.block_documents.read_block_document_by_id(
                session, block_document_id=outer_block_document.id
            )
        )
        assert block_document_after_update.data == {
            "b": {},
            "z": "zzzzz",
        }
        assert block_document_after_update.block_document_references == {}


class TestSecretBlockDocuments:
    @pytest.fixture()
    async def secret_block_type_and_schema(self, session):
        class SecretBlock(Block):
            x: SecretStr
            y: SecretBytes
            z: str

        secret_block_type = await models.block_types.create_block_type(
            session=session, block_type=SecretBlock._to_block_type()
        )
        secret_block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=SecretBlock._to_block_schema(
                block_type_id=secret_block_type.id
            ),
        )

        await session.commit()
        return secret_block_type, secret_block_schema

    @pytest.fixture()
    async def secret_block_document(self, session, secret_block_type_and_schema):
        secret_block_type, secret_block_schema = secret_block_type_and_schema
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="secret-block",
                data=dict(x=X, y=Y, z=Z),
                block_type_id=secret_block_type.id,
                block_schema_id=secret_block_schema.id,
            ),
        )
        await session.commit()
        return block

    async def test_create_secret_block_document_obfuscates_results(
        self, client, secret_block_type_and_schema
    ):
        secret_block_type, secret_block_schema = secret_block_type_and_schema
        response = await client.post(
            "/block_documents/",
            json=schemas.actions.BlockDocumentCreate(
                name="secret-block",
                data=dict(x=X, y=Y, z=Z),
                block_type_id=secret_block_type.id,
                block_schema_id=secret_block_schema.id,
            ).dict(json_compatible=True),
        )
        block = schemas.core.BlockDocument.parse_obj(response.json())

        assert block.data["x"] == obfuscate_string(X)
        assert block.data["y"] == obfuscate_string(Y)
        assert block.data["z"] == Z

        # by default, no characters of secrets are shown
        assert block.data["y"] == "*" * 8

    async def test_read_secret_block_document_by_id_obfuscates_results(
        self, client, secret_block_document
    ):

        response = await client.get(
            f"/block_documents/{secret_block_document.id}",
            params=dict(),
        )
        block = schemas.core.BlockDocument.parse_obj(response.json())

        assert block.data["x"] == obfuscate_string(X)
        assert block.data["y"] == obfuscate_string(Y)
        assert block.data["z"] == Z

    async def test_read_secret_block_document_by_id_with_secrets(
        self, client, secret_block_document
    ):

        response = await client.get(
            f"/block_documents/{secret_block_document.id}",
            params=dict(include_secrets=True),
        )
        block = schemas.core.BlockDocument.parse_obj(response.json())
        assert block.data["x"] == X
        assert block.data["y"] == Y
        assert block.data["z"] == Z

    async def test_read_secret_block_documents_by_name_obfuscates_results(
        self, client, secret_block_document
    ):
        response = await client.get(
            f"/block_types/slug/{secret_block_document.block_type.slug}/block_documents",
            params=dict(),
        )
        blocks = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )

        assert len(blocks) == 1
        assert blocks[0].data["x"] == obfuscate_string(X)
        assert blocks[0].data["y"] == obfuscate_string(Y)
        assert blocks[0].data["z"] == Z

    async def test_read_secret_block_documents_by_name_with_secrets(
        self, client, secret_block_document
    ):

        response = await client.get(
            f"/block_types/slug/{secret_block_document.block_type.slug}/block_documents",
            params=dict(include_secrets=True),
        )
        blocks = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )

        assert len(blocks) == 1
        assert blocks[0].data["x"] == X
        assert blocks[0].data["y"] == Y
        assert blocks[0].data["z"] == Z

    async def test_read_secret_block_document_by_name_obfuscates_results(
        self, client, secret_block_document
    ):
        response = await client.get(
            f"/block_types/slug/{secret_block_document.block_type.slug}/block_documents/name/{secret_block_document.name}",
            params=dict(),
        )
        block = pydantic.parse_obj_as(schemas.core.BlockDocument, response.json())

        assert block.data["x"] == obfuscate_string(X)
        assert block.data["y"] == obfuscate_string(Y)
        assert block.data["z"] == Z

    async def test_read_secret_block_document_by_name_with_secrets(
        self, client, secret_block_document
    ):

        response = await client.get(
            f"/block_types/slug/{secret_block_document.block_type.slug}/block_documents/name/{secret_block_document.name}",
            params=dict(include_secrets=True),
        )
        block = pydantic.parse_obj_as(schemas.core.BlockDocument, response.json())

        assert block.data["x"] == X
        assert block.data["y"] == Y
        assert block.data["z"] == Z

    async def test_read_secret_block_documents_obfuscates_results(
        self, client, secret_block_document
    ):

        response = await client.post(
            f"/block_documents/filter",
            json=dict(),
        )
        blocks = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )

        assert len(blocks) == 1
        assert blocks[0].data["x"] == obfuscate_string(X)
        assert blocks[0].data["y"] == obfuscate_string(Y)
        assert blocks[0].data["z"] == Z

    async def test_read_secret_block_documents_with_secrets(
        self, client, secret_block_document
    ):

        response = await client.post(
            f"/block_documents/filter",
            json=dict(include_secrets=True),
        )
        blocks = pydantic.parse_obj_as(
            List[schemas.core.BlockDocument], response.json()
        )

        assert len(blocks) == 1
        assert blocks[0].data["x"] == X
        assert blocks[0].data["y"] == Y
        assert blocks[0].data["z"] == Z

    async def test_nested_block_secrets_are_obfuscated_when_all_blocks_are_saved(
        self, client, session
    ):
        class ChildBlock(Block):
            x: SecretStr
            y: str

        class ParentBlock(Block):
            a: int
            b: SecretStr
            child: ChildBlock

        # save the child block
        child = ChildBlock(x=X, y=Y)
        await child.save("child")
        # save the parent block
        block = ParentBlock(a=3, b="b", child=child)
        await block.save("nested-test")
        await session.commit()
        response = await client.get(f"/block_documents/{block._block_document_id}")
        block = schemas.core.BlockDocument.parse_obj(response.json())
        assert block.data["a"] == 3
        assert block.data["b"] == obfuscate_string("b")
        assert block.data["child"]["x"] == obfuscate_string(X)
        assert block.data["child"]["y"] == Y

    async def test_nested_block_secrets_are_obfuscated_when_only_top_level_block_is_saved(
        self, client, session
    ):
        class ChildBlock(Block):
            x: SecretStr
            y: str

        class ParentBlock(Block):
            a: int
            b: SecretStr
            child: ChildBlock

        # child block is not saved, but hardcoded into the parent block
        child = ChildBlock(x=X, y=Y)
        # save the parent block
        block = ParentBlock(a=3, b="b", child=child)
        await block.save("nested-test")
        await session.commit()
        response = await client.get(f"/block_documents/{block._block_document_id}")
        block = schemas.core.BlockDocument.parse_obj(response.json())
        assert block.data["a"] == 3
        assert block.data["b"] == obfuscate_string("b")
        assert block.data["child"]["x"] == obfuscate_string(X)
        assert block.data["child"]["y"] == Y

    async def test_nested_block_secrets_are_returned(self, client):
        class ChildBlock(Block):
            x: SecretStr
            y: str

        class ParentBlock(Block):
            a: int
            b: SecretStr
            child: ChildBlock

        block = ParentBlock(a=3, b="b", child=ChildBlock(x=X, y=Y))
        await block.save("nested-test")

        response = await client.get(
            f"/block_documents/{block._block_document_id}",
            params=dict(include_secrets=True),
        )
        block = schemas.core.BlockDocument.parse_obj(response.json())
        assert block.data["a"] == 3
        assert block.data["b"] == "b"
        assert block.data["child"]["x"] == X
        assert block.data["child"]["y"] == Y
