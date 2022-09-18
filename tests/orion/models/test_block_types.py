from textwrap import dedent
from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.filters import BlockSchemaFilter, BlockTypeFilter

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
    async def test_create_block_type(self, session):
        block_type = await models.block_types.create_block_type(
            session=session,
            block_type=schemas.actions.BlockTypeCreate(
                name="x",
                slug="x",
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/documentation.html",
                description="A block, verily",
                code_example=CODE_EXAMPLE,
            ),
        )
        assert block_type.name == "x"
        assert block_type.logo_url == "http://example.com/logo.png"
        assert block_type.documentation_url == "http://example.com/documentation.html"
        assert block_type.description == "A block, verily"
        assert block_type.code_example == CODE_EXAMPLE

        db_block_type = await models.block_types.read_block_type(
            session=session, block_type_id=block_type.id
        )

        assert db_block_type.name == block_type.name
        assert db_block_type.logo_url == block_type.logo_url
        assert db_block_type.documentation_url == block_type.documentation_url
        assert db_block_type.description == block_type.description
        assert db_block_type.code_example == block_type.code_example

    async def test_create_block_type_unique_slug(self, session):
        await models.block_types.create_block_type(
            session=session,
            block_type=schemas.actions.BlockTypeCreate(name="x", slug="x"),
        )
        with pytest.raises(sa.exc.IntegrityError):
            await models.block_types.create_block_type(
                session=session,
                block_type=schemas.actions.BlockTypeCreate(name="x2", slug="x"),
            )

    async def test_create_block_type_same_name_different_slug(self, session):
        await models.block_types.create_block_type(
            session=session,
            block_type=schemas.actions.BlockTypeCreate(name="x", slug="x"),
        )
        await models.block_types.create_block_type(
            session=session,
            block_type=schemas.actions.BlockTypeCreate(name="x", slug="x2"),
        )


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

    async def test_read_block_type_by_id(self, session, block_type_x):
        db_block_type = await models.block_types.read_block_type(
            session=session, block_type_id=block_type_x.id
        )

        assert db_block_type.name == block_type_x.name

    async def test_read_block_type_by_name(self, session, block_type_x):
        db_block_type = await models.block_types.read_block_type_by_slug(
            session=session, block_type_slug=block_type_x.slug
        )

        assert db_block_type.id == block_type_x.id

    async def test_read_nonexistant_block_type(self, session):
        assert not await models.block_types.read_block_type(
            session=session, block_type_id=uuid4()
        )

    async def test_read_nonexistant_block_type_by_name(self, session):
        assert not await models.block_types.read_block_type_by_slug(
            session=session, block_type_slug="huh?"
        )

    async def test_read_all_block_types(
        self, session, block_type_x, block_type_y, block_type_z
    ):
        block_types = await models.block_types.read_block_types(session=session)

        assert {block_type.id for block_type in block_types} == {
            block_type.id for block_type in [block_type_x, block_type_y, block_type_z]
        }
        assert [block_type.id for block_type in block_types] == [
            block_type_x.id,
            block_type_y.id,
            block_type_z.id,
        ]

    async def test_read_block_types_with_limit_and_offset(
        self, session, block_type_x, block_type_y, block_type_z
    ):
        block_types = await models.block_types.read_block_types(
            session=session, limit=1
        )

        assert len(block_types) == 1
        assert [block_type.id for block_type in block_types] == [block_type_x.id]

        block_types = await models.block_types.read_block_types(
            session=session, limit=2, offset=1
        )

        assert len(block_types) == 2
        assert [block_type.id for block_type in block_types] == [
            block_type_y.id,
            block_type_z.id,
        ]

        block_types = await models.block_types.read_block_types(
            session=session, offset=3
        )

        assert len(block_types) == 0

    async def test_read_block_types_filter_by_name(
        self, session, block_types_with_associated_capabilities
    ):
        block_types = await models.block_types.read_block_types(
            session=session, block_type_filter=BlockTypeFilter(name=dict(like_="duck"))
        )

        assert len(block_types) == 1
        assert block_types == [block_types_with_associated_capabilities[0]]

        block_types = await models.block_types.read_block_types(
            session=session, block_type_filter=BlockTypeFilter(name=dict(like_="c"))
        )

        assert len(block_types) == 2
        assert block_types == [
            block_types_with_associated_capabilities[2],
            block_types_with_associated_capabilities[0],
        ]

        block_types = await models.block_types.read_block_types(
            session=session, block_type_filter=BlockTypeFilter(name=dict(like_="z"))
        )

        assert len(block_types) == 0

    async def test_read_block_types_filter_by_associated_capability(
        self, session, block_types_with_associated_capabilities
    ):
        fly_and_swim_block_types = await models.block_types.read_block_types(
            session=session,
            block_schema_filter=BlockSchemaFilter(
                block_capabilities=dict(all_=["fly", "swim"])
            ),
        )
        assert len(fly_and_swim_block_types) == 1
        assert fly_and_swim_block_types == [block_types_with_associated_capabilities[0]]

        fly_block_types = await models.block_types.read_block_types(
            session=session,
            block_schema_filter=BlockSchemaFilter(
                block_capabilities=dict(all_=["fly"])
            ),
        )
        assert len(fly_block_types) == 2
        assert fly_block_types == [
            block_types_with_associated_capabilities[1],
            block_types_with_associated_capabilities[0],
        ]

        swim_block_types = await models.block_types.read_block_types(
            session=session,
            block_schema_filter=BlockSchemaFilter(
                block_capabilities=dict(all_=["swim"])
            ),
        )
        assert len(swim_block_types) == 1
        assert swim_block_types == [block_types_with_associated_capabilities[0]]


class TestUpdateBlockType:
    async def test_update_block_type(self, session, block_type_x):
        assert await models.block_types.update_block_type(
            session,
            block_type_id=block_type_x.id,
            block_type=schemas.actions.BlockTypeUpdate(
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/documentation.html",
                description="A block, verily",
                code_example=CODE_EXAMPLE,
            ),
        )

        db_block_type = await models.block_types.read_block_type(
            session=session, block_type_id=block_type_x.id
        )

        assert db_block_type.logo_url == "http://example.com/logo.png"
        assert (
            db_block_type.documentation_url == "http://example.com/documentation.html"
        )
        assert db_block_type.description == "A block, verily"
        assert db_block_type.code_example == CODE_EXAMPLE

    async def test_update_nonexistant_block_type(self, session):
        assert not await models.block_types.update_block_type(
            session,
            block_type_id=uuid4(),
            block_type=schemas.actions.BlockTypeUpdate(
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/documentation.html",
            ),
        )


class TestDeleteBlockType:
    async def test_delete_block_type(self, session, block_type_x):

        await models.block_types.delete_block_type(
            session=session, block_type_id=block_type_x.id
        )
        assert not await models.block_types.read_block_type(
            session=session, block_type_id=block_type_x.id
        )

    async def test_delete_nonexistant_block_type(self, session):
        assert not await models.block_types.delete_block_type(
            session=session, block_type_id=uuid4()
        )
