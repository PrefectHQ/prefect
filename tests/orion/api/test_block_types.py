from textwrap import dedent
from typing import List
from uuid import uuid4

import pydantic
import pytest
from fastapi import status

from prefect.orion.schemas.actions import BlockTypeCreate, BlockTypeUpdate
from prefect.orion.schemas.core import BlockDocument, BlockType
from tests.orion.models.test_block_types import CODE_EXAMPLE

CODE_EXAMPLE = dedent(
    """\
        ```python
        from prefect_collection import CoolBlock

        rad_block = await CoolBlock.load("rad")
        rad_block.crush()
        ```
        """
)


class TestCreateBlockType:
    async def test_create_block_type(self, client):
        response = await client.post(
            "/block_types/",
            json=BlockTypeCreate(
                name="x",
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/docs.html",
                description="A block, verily",
                code_example=CODE_EXAMPLE,
            ).dict(),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = BlockType.parse_obj(response.json())

        assert result.name == "x"
        assert result.logo_url == "http://example.com/logo.png"
        assert result.documentation_url == "http://example.com/docs.html"
        assert result.description == "A block, verily"
        assert result.code_example == CODE_EXAMPLE

        response = await client.get(f"/block_types/{result.id}")
        api_block_type = BlockType.parse_obj(response.json())
        assert api_block_type.name == "x"
        assert api_block_type.logo_url == "http://example.com/logo.png"
        assert api_block_type.documentation_url == "http://example.com/docs.html"
        assert api_block_type.description == "A block, verily"
        assert api_block_type.code_example == CODE_EXAMPLE

    async def test_create_block_type_with_existing_name(self, client):
        response = await client.post(
            "/block_types/",
            json=BlockTypeCreate(
                name="x",
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/docs.html",
            ).dict(),
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/block_types/",
            json=BlockTypeCreate(
                name="x",
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/docs.html",
            ).dict(),
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.parametrize(
        "name",
        [
            "my block type",
            "my:block type",
            r"my\block type",
            "my👍block type",
            "my|block type",
        ],
    )
    async def test_create_block_type_with_nonstandard_characters(self, client, name):
        response = await client.post(
            "/block_types/",
            json=dict(
                name=name,
            ),
        )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize(
        "name",
        [
            "my%block_type",
            "my/block type",
        ],
    )
    async def test_create_block_type_with_invalid_characters(self, client, name):
        response = await client.post(
            "/block_types/",
            json=dict(
                name=name,
            ),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestReadBlockType:
    async def test_read_block_type_by_id(self, client, block_type_x):
        response = await client.get(f"/block_types/{block_type_x.id}")
        assert response.status_code == status.HTTP_200_OK
        result = BlockType.parse_obj(response.json())
        assert result.name == block_type_x.name
        assert result.id == block_type_x.id

    async def test_read_block_type_by_name(self, client, block_type_x):
        response = await client.get(f"/block_types/name/{block_type_x.name}")
        assert response.status_code == status.HTTP_200_OK
        result = BlockType.parse_obj(response.json())
        assert result.name == block_type_x.name
        assert result.id == block_type_x.id

    async def test_read_missing_block_type_by_name(self, client):
        response = await client.get("/block_types/name/not a real block")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadBlockTypes:
    async def test_read_block_types(
        self, client, block_type_x, block_type_y, block_type_z
    ):
        response = await client.post("/block_types/filter")
        assert response.status_code == status.HTTP_200_OK
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert [block_type.id for block_type in read_block_types] == [
            block_type_x.id,
            block_type_y.id,
            block_type_z.id,
        ]

    async def test_read_block_types_with_limit_and_offset(
        self, client, block_type_x, block_type_y, block_type_z
    ):
        response = await client.post("/block_types/filter", json=dict(limit=2))
        assert response.status_code == status.HTTP_200_OK
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert [block_type.id for block_type in read_block_types] == [
            block_type_x.id,
            block_type_y.id,
        ]

        response = await client.post("/block_types/filter", json=dict(offset=2))
        assert response.status_code == status.HTTP_200_OK
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert [block_type.id for block_type in read_block_types] == [
            block_type_z.id,
        ]


class TestUpdateBlockType:
    async def test_update_block_type(self, client, block_type_x):
        response = await client.patch(
            f"/block_types/{block_type_x.id}",
            json=BlockTypeUpdate(
                logo_url="http://foo.com/bar.png",
                documentation_url="http://foo.com/bar.html",
                description="A block, verily",
                code_example=CODE_EXAMPLE,
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/block_types/{block_type_x.id}")
        assert response.status_code == status.HTTP_200_OK
        updated_block = BlockType.parse_obj(response.json())

        assert updated_block.name == block_type_x.name
        assert updated_block.logo_url == "http://foo.com/bar.png"
        assert updated_block.documentation_url == "http://foo.com/bar.html"
        assert updated_block.description == "A block, verily"
        assert updated_block.code_example == CODE_EXAMPLE

    async def test_update_nonexistent_block_type(self, client):
        response = await client.patch(
            f"/block_types/{uuid4()}",
            json=BlockTypeUpdate(
                logo_url="http://foo.com/bar.png",
                documentation_url="http://foo.com/bar.html",
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteBlockType:
    async def test_delete_block_type(self, client, block_type_x):
        response = await client.delete(f"/block_types/{block_type_x.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/block_types/{block_type_x.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_nonexistent_block_type(self, client):
        response = await client.delete(f"/block_types/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadBlockDocumentsForBlockType:
    async def test_read_block_documents_for_block_type(
        self, client, block_type_x, block_document
    ):
        response = await client.get(
            f"/block_types/name/{block_type_x.name}/block_documents"
        )
        assert response.status_code == status.HTTP_200_OK

        read_block_documents = pydantic.parse_obj_as(
            List[BlockDocument], response.json()
        )
        assert [block_doc.id for block_doc in read_block_documents] == [
            block_document.id
        ]

    async def test_read_block_documents_for_nonexistant_block_type(self, client):
        response = await client.get(f"/block_types/name/nonsense/block_documents")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadBlockDocumentByNameForBlockType:
    async def test_read_block_document_for_block_type(
        self, client, block_type_x, block_document
    ):
        response = await client.get(
            f"/block_types/name/{block_type_x.name}/block_documents/name/{block_document.name}"
        )
        assert response.status_code == status.HTTP_200_OK

        read_block_document = BlockDocument.parse_obj(response.json())
        assert read_block_document.id == block_document.id
        assert read_block_document.name == block_document.name

    async def test_read_block_document_for_nonexistant_block_type(
        self, client, block_document
    ):
        response = await client.get(
            f"/block_types/name/nonsense/block_documents/name/{block_document.name}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_block_document_for_nonexistant_block_document(
        self, client, block_type_x
    ):
        response = await client.get(
            f"/block_types/name/{block_type_x.name}/block_documents/name/nonsense"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
