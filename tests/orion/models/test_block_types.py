from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


class TestCreateBlockType:
    async def test_create_block_type(self, session):
        block_type = await models.block_types.create_block_type(
            session=session,
            block_type=schemas.actions.BlockTypeCreate(
                name="x",
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/documentation.html",
            ),
        )
        assert block_type.name == "x"
        assert block_type.logo_url == "http://example.com/logo.png"
        assert block_type.documentation_url == "http://example.com/documentation.html"

        db_block_type = await models.block_types.read_block_type(
            session=session, block_type_id=block_type.id
        )

        assert db_block_type.name == block_type.name
        assert db_block_type.logo_url == block_type.logo_url
        assert db_block_type.documentation_url == block_type.documentation_url

    async def test_create_block_type_unique_name(self, session):
        await models.block_types.create_block_type(
            session=session,
            block_type=schemas.actions.BlockTypeCreate(
                name="x",
            ),
        )
        with pytest.raises(sa.exc.IntegrityError):
            await models.block_types.create_block_type(
                session=session,
                block_type=schemas.actions.BlockTypeCreate(
                    name="x",
                ),
            )


class TestReadBlockTypes:
    async def test_read_block_type_by_id(self, session, block_type_x):
        db_block_type = await models.block_types.read_block_type(
            session=session, block_type_id=block_type_x.id
        )

        assert db_block_type.name == block_type_x.name

    async def test_read_block_type_by_name(self, session, block_type_x):
        db_block_type = await models.block_types.read_block_type_by_name(
            session=session, block_type_name=block_type_x.name
        )

        assert db_block_type.id == block_type_x.id

    async def test_read_nonexistant_block_type(self, session):
        assert not await models.block_types.read_block_type(
            session=session, block_type_id=uuid4()
        )

    async def test_read_nonexistant_block_type_by_name(self, session):
        assert not await models.block_types.read_block_type_by_name(
            session=session, block_type_name="huh?"
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


class TestUpdateBlockType:
    async def test_update_block_type(self, session, block_type_x):
        assert await models.block_types.update_block_type(
            session,
            block_type_id=block_type_x.id,
            block_type=schemas.actions.BlockTypeUpdate(
                logo_url="http://example.com/logo.png",
                documentation_url="http://example.com/documentation.html",
            ),
        )

        db_block_type = await models.block_types.read_block_type(
            session=session, block_type_id=block_type_x.id
        )

        assert db_block_type.logo_url == "http://example.com/logo.png"
        assert (
            db_block_type.documentation_url == "http://example.com/documentation.html"
        )

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
