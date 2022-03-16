import os
import time
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken

from prefect.orion import models, schemas
from prefect.orion.schemas.core import Block


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


class TestReadBlocks:
    @pytest.fixture(autouse=True)
    async def blocks(self, session, block_specs):

        blocks = []
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[0].id, name="Block 1"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[1].id, name="Block 2"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[2].id, name="Block 3"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[1].id, name="Block 4"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[2].id, name="Block 5"
                ),
            )
        )

        session.add_all(blocks)
        await session.commit()
        return blocks

    async def test_read_blocks(self, session, blocks):
        read_blocks = await models.blocks.read_blocks(session=session)
        assert {b.id for b in read_blocks} == {b.id for b in blocks}
        # sorted by block spec name, block spec version (desc), block name
        assert [b.id for b in read_blocks] == [
            blocks[2].id,
            blocks[4].id,
            blocks[0].id,
            blocks[1].id,
            blocks[3].id,
        ]

    async def test_read_blocks_limit_offset(self, session, blocks):
        # sorted by block spec name, block spec version (desc), block name
        read_blocks = await models.blocks.read_blocks(session=session, limit=2)
        assert [b.id for b in read_blocks] == [blocks[2].id, blocks[4].id]
        read_blocks = await models.blocks.read_blocks(
            session=session, limit=2, offset=2
        )
        assert [b.id for b in read_blocks] == [blocks[0].id, blocks[1].id]

    async def test_read_blocks_by_type(self, session, blocks):
        read_blocks = await models.blocks.read_blocks(
            session=session, block_spec_type="abc"
        )
        assert [b.id for b in read_blocks] == [blocks[0].id, blocks[1].id, blocks[3].id]


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


class TestDefaultStorage:
    @pytest.fixture
    async def storage_block_spec(self, session):
        storage_block_spec = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="storage-type",
                version="1.0",
                type="STORAGE",
            ),
        )
        await session.commit()
        return storage_block_spec

    @pytest.fixture
    async def storage_block(self, session, storage_block_spec):
        block = await models.blocks.create_block(
            session=session,
            block=Block(
                name="storage", data=dict(), block_spec_id=storage_block_spec.id
            ),
        )
        await session.commit()
        return block

    async def test_set_default_storage_block(self, session, storage_block):
        assert not await models.blocks.get_default_storage_block(session=session)

        await models.blocks.set_default_storage_block(
            session=session, block_id=storage_block.id
        )

        result = await models.blocks.get_default_storage_block(session=session)
        assert result.id == storage_block.id

    async def test_set_default_fails_if_not_storage_block(self, session, block_specs):
        non_storage_block = await models.blocks.create_block(
            session=session,
            block=Block(
                name="non-storage", data=dict(), block_spec_id=block_specs[0].id
            ),
        )
        await session.commit()

        with pytest.raises(ValueError, match="(Block spec type must be STORAGE)"):
            await models.blocks.set_default_storage_block(
                session=session, block_id=non_storage_block.id
            )
        assert not await models.blocks.get_default_storage_block(session=session)

    async def test_clear_default_storage_block(self, session, storage_block):

        await models.blocks.set_default_storage_block(
            session=session, block_id=storage_block.id
        )
        result = await models.blocks.get_default_storage_block(session=session)
        assert result.id == storage_block.id

        await models.blocks.clear_default_storage_block(session=session)

        assert not await models.blocks.get_default_storage_block(session=session)

    async def test_set_default_storage_block_clears_old_block(
        self, session, storage_block, storage_block_spec, db
    ):
        storage_block_2 = await models.blocks.create_block(
            session=session,
            block=Block(
                name="storage-2", data=dict(), block_spec_id=storage_block_spec.id
            ),
        )
        await session.commit()

        await models.blocks.set_default_storage_block(
            session=session, block_id=storage_block.id
        )

        result = await session.execute(
            sa.select(db.Block).where(db.Block.is_default_storage_block.is_(True))
        )
        default_blocks = result.scalars().unique().all()
        assert len(default_blocks) == 1
        assert default_blocks[0].id == storage_block.id

        await models.blocks.set_default_storage_block(
            session=session, block_id=storage_block_2.id
        )

        result = await session.execute(
            sa.select(db.Block).where(db.Block.is_default_storage_block.is_(True))
        )
        default_blocks = result.scalars().unique().all()
        assert len(default_blocks) == 1
        assert default_blocks[0].id == storage_block_2.id
