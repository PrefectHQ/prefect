import os
import time
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken

from prefect.orion import models, schemas


@pytest.fixture
async def block_specs(session):
    block_spec_0 = await models.block_specs.create_block_spec(
        session=session,
        block_spec=schemas.core.BlockSpec(
            name="x",
            version="1.0",
            type="abc",
        ),
    )
    await session.commit()

    block_spec_1 = await models.block_specs.create_block_spec(
        session=session,
        block_spec=schemas.core.BlockSpec(
            name="y",
            version="1.0",
            type="abc",
        ),
    )
    await session.commit()

    block_spec_2 = await models.block_specs.create_block_spec(
        session=session,
        block_spec=schemas.core.BlockSpec(
            name="x",
            version="2.0",
            type=None,
        ),
    )
    await session.commit()

    return block_spec_0, block_spec_1, block_spec_2


class TestCreateBlock:
    async def test_create_block(self, session, block_specs):
        result = await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(y=1), block_spec_id=block_specs[0].id
            ),
        )
        await session.commit()

        assert result.name == "x"
        assert result.data != dict(y=1)
        assert await result.decrypt_data(session) == dict(y=1)
        assert result.block_spec_id == block_specs[0].id
        assert result.block_spec.name == block_specs[0].name

        db_block = await models.blocks.read_block_by_id(
            session=session, block_id=result.id
        )
        assert db_block.id == result.id

    async def test_create_block_with_same_name_as_existing_block(
        self, session, block_specs
    ):
        assert await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[0].id
            ),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    name="x", data=dict(), block_spec_id=block_specs[0].id
                ),
            )

    async def test_create_block_with_same_name_as_existing_block_but_different_block_spec(
        self, session, block_specs
    ):
        assert await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[0].id
            ),
        )

        assert await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[1].id
            ),
        )


class TestReadBlock:
    async def test_read_block_by_id(self, session, block_specs):
        block = await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[0].id
            ),
        )

        result = await models.blocks.read_block_by_id(
            session=session, block_id=block.id
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_spec_id == block_specs[0].id

    async def test_read_block_by_id_doesnt_exist(self, session):
        assert not await models.blocks.read_block_by_id(
            session=session, block_id=uuid4()
        )

    async def test_read_block_by_name_with_no_version(self, session, block_specs):
        block = await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[0].id
            ),
        )

        result = await models.blocks.read_block_by_name(
            session=session, name=block.name, block_spec_name=block_specs[0].name
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_spec_id == block_specs[0].id

    async def test_read_block_by_name_with_version(self, session, block_specs):
        block = await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[0].id
            ),
        )

        result = await models.blocks.read_block_by_name(
            session=session,
            name=block.name,
            block_spec_name=block_specs[0].name,
            block_spec_version=block_specs[0].version,
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_spec_id == block_specs[0].id

    async def test_read_block_by_name_doesnt_exist(self, session):
        assert not await models.blocks.read_block_by_name(
            session=session, name="x", block_spec_name="not-here"
        )

    async def test_read_block_by_name_with_wrong_version(self, session, block_specs):
        block = await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[0].id
            ),
        )

        assert not await models.blocks.read_block_by_name(
            session=session,
            name=block.name,
            block_spec_name=block_specs[0].name,
            block_spec_version="17.1",
        )


class TestDeleteBlock:
    async def test_delete_block(self, session, block_specs):
        block = await models.blocks.create_block(
            session=session,
            block=schemas.core.Block(
                name="x", data=dict(), block_spec_id=block_specs[0].id
            ),
        )

        block_id = block.id

        await models.blocks.delete_block(session=session, block_id=block_id)
        assert not await models.blocks.read_block_by_id(
            session=session, block_id=block_id
        )

    async def test_delete_nonexistant_block(self, session, block_specs):
        assert not await models.blocks.delete_block(session=session, block_id=uuid4())
