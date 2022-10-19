from textwrap import dedent
from typing import List
from uuid import uuid4

import pendulum
import pydantic
import pytest
from fastapi import status

import prefect
from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockTypeCreate, BlockTypeUpdate
from prefect.orion.schemas.core import BlockDocument, BlockType
from prefect.utilities.slugify import slugify
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


@pytest.fixture
async def system_block_type(session):
    block_type = await models.block_types.create_block_type(
        session=session,
        block_type=schemas.core.BlockType(
            name="system_block", slug="system-block", is_protected=True
        ),
    )
    await session.commit()
    return block_type


class TestCreateBlockType:
    async def test_create_block_type(self, client):
        response = await client.post(
            "/block_types/",
            json=BlockTypeCreate(
                name="x",
                slug="x",
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/docs.html",
                description="A block, verily",
                code_example=CODE_EXAMPLE,
            ).dict(),
        )
        assert response.status_code == status.HTTP_201_CREATED
        result = BlockType.parse_obj(response.json())

        assert result.name == "x"
        assert result.slug == "x"
        assert result.logo_url == "http://example.com/logo.png"
        assert result.documentation_url == "http://example.com/docs.html"
        assert result.description == "A block, verily"
        assert result.code_example == CODE_EXAMPLE

        response = await client.get(f"/block_types/{result.id}")
        api_block_type = BlockType.parse_obj(response.json())
        assert api_block_type.name == "x"
        assert api_block_type.slug == "x"
        assert api_block_type.logo_url == "http://example.com/logo.png"
        assert api_block_type.documentation_url == "http://example.com/docs.html"
        assert api_block_type.description == "A block, verily"
        assert api_block_type.code_example == CODE_EXAMPLE

    async def test_create_block_type_with_existing_slug(self, client):
        response = await client.post(
            "/block_types/",
            json=BlockTypeCreate(
                name="x",
                slug="x",
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/docs.html",
            ).dict(),
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/block_types/",
            json=BlockTypeCreate(
                name="x",
                slug="x",
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
            json=dict(name=name, slug=slugify(name)),
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
            json=dict(name=name, slug=slugify(name)),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize(
        "name", ["PrefectBlockType", "Prefect", "prefect_block_type", "pReFeCt!"]
    )
    async def test_create_block_type_with_reserved_name_fails(self, client, name):
        response = await client.post(
            "/block_types/",
            json=dict(name=name, slug=slugify(name)),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "Block type names beginning with 'Prefect' are reserved."
        )

    async def test_create_block_type_with_invalid_slug_fails(self, client):
        response = await client.post(
            "/block_types/",
            json=dict(name="bad slug", slug="bad slug"),
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestReadBlockType:
    async def test_read_block_type_by_id(self, client, block_type_x):
        response = await client.get(f"/block_types/{block_type_x.id}")
        assert response.status_code == status.HTTP_200_OK
        result = BlockType.parse_obj(response.json())
        assert result.name == block_type_x.name
        assert result.id == block_type_x.id

    async def test_read_block_type_by_slug(self, client, block_type_x):
        response = await client.get(f"/block_types/slug/{block_type_x.slug}")
        assert response.status_code == status.HTTP_200_OK
        result = BlockType.parse_obj(response.json())
        assert result.name == block_type_x.name
        assert result.id == block_type_x.id

    async def test_read_missing_block_type_by_name(self, client):
        response = await client.get("/block_types/slug/not-a-real-block")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadBlockTypes:
    @pytest.fixture
    async def block_types_with_associated_capabilities(self, session):
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

        class Duck(CanSwim, CanFly, Block):
            a: str

        class Bird(CanFly, Block):
            b: str

        class Cat(CanRun, Block):
            c: str

        block_type_duck = await models.block_types.create_block_type(
            session=session, block_type=Duck._to_block_type()
        )
        block_schema_duck = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=Duck._to_block_schema(block_type_id=block_type_duck.id),
        )
        block_type_bird = await models.block_types.create_block_type(
            session=session, block_type=Bird._to_block_type()
        )
        block_schema_bird = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=Bird._to_block_schema(block_type_id=block_type_bird.id),
        )
        block_type_cat = await models.block_types.create_block_type(
            session=session, block_type=Cat._to_block_type()
        )
        block_schema_cat = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=Cat._to_block_schema(block_type_id=block_type_cat.id),
        )

        await session.commit()

        return block_type_duck, block_type_bird, block_type_cat

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

    async def test_read_block_types_filter_by_name(
        self, client, block_types_with_associated_capabilities
    ):
        response = await client.post(
            "/block_types/filter", json=dict(block_types=dict(name=dict(like_="duck")))
        )

        assert response.status_code == 200
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(read_block_types) == 1
        assert read_block_types[0].id == block_types_with_associated_capabilities[0].id

        response = await client.post(
            "/block_types/filter", json=dict(block_types=dict(name=dict(like_="c")))
        )

        assert response.status_code == 200
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(read_block_types) == 2
        assert [b.id for b in read_block_types] == [
            block_types_with_associated_capabilities[2].id,
            block_types_with_associated_capabilities[0].id,
        ]

        response = await client.post(
            "/block_types/filter", json=dict(block_types=dict(name=dict(like_="z")))
        )
        assert response.status_code == 200
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())

    async def test_read_block_types_filter_by_associated_capability(
        self, client, block_types_with_associated_capabilities
    ):
        response = await client.post(
            "/block_types/filter",
            json=dict(
                block_schemas=dict(block_capabilities=dict(all_=["fly", "swim"]))
            ),
        )

        assert response.status_code == 200
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(read_block_types) == 1
        assert read_block_types[0].id == block_types_with_associated_capabilities[0].id

        response = await client.post(
            "/block_types/filter",
            json=dict(block_schemas=dict(block_capabilities=dict(all_=["fly"]))),
        )

        assert response.status_code == 200
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(read_block_types) == 2
        assert [b.id for b in read_block_types] == [
            block_types_with_associated_capabilities[1].id,
            block_types_with_associated_capabilities[0].id,
        ]

        response = await client.post(
            "/block_types/filter",
            json=dict(block_schemas=dict(block_capabilities=dict(all_=["swim"]))),
        )
        assert response.status_code == 200
        read_block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(read_block_types) == 1
        assert read_block_types[0].id == block_types_with_associated_capabilities[0].id


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

    async def test_update_system_block_type_succeeds(self, system_block_type, client):
        response = await client.patch(
            f"/block_types/{system_block_type.id}",
            json=BlockTypeUpdate(
                description="Hi there!",
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestDeleteBlockType:
    async def test_delete_block_type(self, client, block_type_x):
        response = await client.delete(f"/block_types/{block_type_x.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        response = await client.get(f"/block_types/{block_type_x.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_nonexistent_block_type(self, client):
        response = await client.delete(f"/block_types/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_system_block_type_fails(self, system_block_type, client):
        response = await client.delete(f"/block_types/{system_block_type.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "protected block types cannot be deleted."


class TestReadBlockDocumentsForBlockType:
    async def test_read_block_documents_for_block_type(
        self, client, block_type_x, block_document
    ):
        response = await client.get(
            f"/block_types/slug/{block_type_x.slug}/block_documents"
        )
        assert response.status_code == status.HTTP_200_OK

        read_block_documents = pydantic.parse_obj_as(
            List[BlockDocument], response.json()
        )
        assert [block_doc.id for block_doc in read_block_documents] == [
            block_document.id
        ]

    async def test_read_block_documents_for_nonexistent_block_type(self, client):
        response = await client.get(f"/block_types/slug/nonsense/block_documents")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadBlockDocumentByNameForBlockType:
    async def test_read_block_document_for_block_type(
        self, client, block_type_x, block_document
    ):
        response = await client.get(
            f"/block_types/slug/{block_type_x.slug}/block_documents/name/{block_document.name}"
        )
        assert response.status_code == status.HTTP_200_OK

        read_block_document = BlockDocument.parse_obj(response.json())
        assert read_block_document.id == block_document.id
        assert read_block_document.name == block_document.name

    async def test_read_block_document_for_nonexistent_block_type(
        self, client, block_document
    ):
        response = await client.get(
            f"/block_types/slug/nonsense/block_documents/name/{block_document.name}"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_read_block_document_for_nonexistent_block_document(
        self, client, block_type_x
    ):
        response = await client.get(
            f"/block_types/slug/{block_type_x.slug}/block_documents/name/nonsense"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSystemBlockTypes:
    async def test_install_system_block_types(self, client):

        response = await client.post("/block_types/filter")
        block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(block_types) == 0

        r = await client.post("/block_types/install_system_block_types")
        assert r.status_code == status.HTTP_200_OK

        response = await client.post("/block_types/filter")
        block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(block_types) > 0

    async def test_install_system_block_types_multiple_times(self, client):

        response = await client.post("/block_types/filter")
        block_types = pydantic.parse_obj_as(List[BlockType], response.json())
        assert len(block_types) == 0

        await client.post("/block_types/install_system_block_types")
        await client.post("/block_types/install_system_block_types")
        await client.post("/block_types/install_system_block_types")

    async def test_create_system_block_type(self, client, session):
        # install system blocks
        await client.post("/block_types/install_system_block_types")

        # create a datetime block
        datetime_block_type = await client.get("/block_types/slug/date-time")
        datetime_block_schema = await client.post(
            "/block_schemas/filter",
            json=dict(
                block_schemas=dict(
                    block_type_id=dict(any_=[datetime_block_type.json()["id"]])
                ),
                limit=1,
            ),
        )
        block = prefect.blocks.system.DateTime(value="2022-01-01T00:00:00+00:00")
        response = await client.post(
            "/block_documents/",
            json=block._to_block_document(
                name="my-test-date-time",
                block_type_id=datetime_block_type.json()["id"],
                block_schema_id=datetime_block_schema.json()[0]["id"],
            ).dict(
                json_compatible=True,
                exclude_unset=True,
                exclude={"id", "block_schema", "block_type"},
            ),
        )
        assert response.status_code == status.HTTP_201_CREATED

        # load the datetime block
        api_block = await prefect.blocks.system.DateTime.load("my-test-date-time")
        assert api_block.value == pendulum.datetime(2022, 1, 1, tz="UTC")

    async def test_system_block_types_are_protected(self, client, session):
        # install system blocks
        await client.post("/block_types/install_system_block_types")
        # read date-time system block
        response = await client.get(f"/block_types/slug/date-time")
        assert response.json()["is_protected"]
