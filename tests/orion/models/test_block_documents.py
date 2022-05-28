import os
import time
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken

from prefect.orion import models, schemas
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
    async def test_create_block_document(self, session, block_schemas):
        result = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(y=1),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )
        await session.commit()

        assert result.name == "x"
        assert result.data != dict(y=1)
        assert await result.decrypt_data(session) == dict(y=1)
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_schema.checksum == block_schemas[0].checksum

        db_block = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=result.id
        )
        assert db_block.id == result.id

    async def test_create_block_with_same_name_as_existing_block(
        self, session, block_schemas
    ):
        assert await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    name="x",
                    data=dict(),
                    block_schema_id=block_schemas[0].id,
                    block_type_id=block_schemas[0].block_type_id,
                ),
            )

    async def test_create_block_with_same_name_as_existing_block_but_different_block_schema(
        self, session, block_schemas
    ):
        assert await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        assert await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[1].id,
                block_type_id=block_schemas[1].block_type_id,
            ),
        )


class TestReadBlock:
    async def test_read_block_by_id(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        result = await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=block.id
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_schema_id == block_schemas[0].id
        assert result.block_type_id == block_schemas[0].block_type_id

    async def test_read_block_by_id_doesnt_exist(self, session):
        assert not await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=uuid4()
        )

    async def test_read_block_by_name_with_no_version(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        result = await models.block_documents.read_block_document_by_name(
            session=session,
            name=block.name,
            block_type_name=block_schemas[0].block_type.name,
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_schema_id == block_schemas[0].id

    async def test_read_block_by_name_with_checksum(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        result = await models.block_documents.read_block_document_by_name(
            session=session,
            name=block.name,
            block_type_name=block_schemas[0].block_type.name,
            block_schema_checksum=block_schemas[0].checksum,
        )
        assert result.id == block.id
        assert result.name == block.name
        assert result.block_schema_id == block_schemas[0].id

    async def test_read_block_by_name_doesnt_exist(self, session):
        assert not await models.block_documents.read_block_document_by_name(
            session=session, name="x", block_type_name="not-here"
        )

    async def test_read_block_by_name_with_wrong_checksum(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        assert not await models.block_documents.read_block_document_by_name(
            session=session,
            name=block.name,
            block_type_name=block_schemas[0].block_type.name,
            block_schema_checksum="not4realchecksum",
        )


class TestReadBlocks:
    @pytest.fixture(autouse=True)
    async def blocks(self, session, block_schemas):

        blocks = []
        blocks.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[0].id,
                    name="Block 1",
                    block_type_id=block_schemas[0].block_type_id,
                ),
            )
        )
        blocks.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="Block 2",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        blocks.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="Block 3",
                    block_type_id=block_schemas[2].block_type_id,
                ),
            )
        )
        blocks.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[1].id,
                    name="Block 4",
                    block_type_id=block_schemas[1].block_type_id,
                ),
            )
        )
        blocks.append(
            await models.block_documents.create_block_document(
                session=session,
                block_document=schemas.actions.BlockDocumentCreate(
                    block_schema_id=block_schemas[2].id,
                    name="Block 5",
                    block_type_id=block_schemas[2].block_type_id,
                ),
            )
        )

        session.add_all(blocks)
        await session.commit()
        return blocks

    async def test_read_blocks(self, session, blocks):
        read_blocks = await models.block_documents.read_block_documents(session=session)
        assert {b.id for b in read_blocks} == {b.id for b in blocks}
        # sorted by block type name, block name
        assert [b.id for b in read_blocks] == [
            blocks[0].id,
            blocks[2].id,
            blocks[4].id,
            blocks[1].id,
            blocks[3].id,
        ]

    async def test_read_blocks_limit_offset(self, session, blocks):
        # sorted by block type name, block name
        read_blocks = await models.block_documents.read_block_documents(
            session=session, limit=2
        )
        assert [b.id for b in read_blocks] == [blocks[0].id, blocks[2].id]
        read_blocks = await models.block_documents.read_block_documents(
            session=session, limit=2, offset=2
        )
        assert [b.id for b in read_blocks] == [blocks[4].id, blocks[1].id]


class TestDeleteBlock:
    async def test_delete_block(self, session, block_schemas):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="x",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )

        block_document_id = block.id

        await models.block_documents.delete_block_document(
            session=session, block_document_id=block_document_id
        )
        assert not await models.block_documents.read_block_document_by_id(
            session=session, block_document_id=block_document_id
        )

    async def test_delete_nonexistant_block(self, session, block_schemas):
        assert not await models.block_documents.delete_block_document(
            session=session, block_document_id=uuid4()
        )


class TestDefaultStorage:
    @pytest.fixture
    async def storage_block_schema(self, session, block_type_x):
        storage_block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                block_type_id=block_type_x.id, fields={}, capabilities=["storage"]
            ),
        )
        await session.commit()
        return storage_block_schema

    @pytest.fixture
    async def storage_block(self, session, storage_block_schema):
        block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="storage",
                data=dict(),
                block_schema_id=storage_block_schema.id,
                block_type_id=storage_block_schema.block_type_id,
            ),
        )
        await session.commit()
        return block

    async def test_set_default_storage_block_document(self, session, storage_block):
        assert not await models.block_documents.get_default_storage_block_document(
            session=session
        )

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block.id
        )

        result = await models.block_documents.get_default_storage_block_document(
            session=session
        )
        assert result.id == storage_block.id

    async def test_set_default_fails_if_not_storage_block(self, session, block_schemas):
        non_storage_block = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="non-storage",
                data=dict(),
                block_schema_id=block_schemas[0].id,
                block_type_id=block_schemas[0].block_type_id,
            ),
        )
        await session.commit()

        with pytest.raises(
            ValueError, match="Block schema must have the 'storage' capability"
        ):
            await models.block_documents.set_default_storage_block_document(
                session=session, block_document_id=non_storage_block.id
            )
        assert not await models.block_documents.get_default_storage_block_document(
            session=session
        )

    async def test_clear_default_storage_block_document(self, session, storage_block):

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block.id
        )
        result = await models.block_documents.get_default_storage_block_document(
            session=session
        )
        assert result.id == storage_block.id

        await models.block_documents.clear_default_storage_block_document(
            session=session
        )

        assert not await models.block_documents.get_default_storage_block_document(
            session=session
        )

    async def test_set_default_storage_block_clears_old_block(
        self, session, storage_block, storage_block_schema, db
    ):
        storage_block_2 = await models.block_documents.create_block_document(
            session=session,
            block_document=schemas.actions.BlockDocumentCreate(
                name="storage-2",
                data=dict(),
                block_schema_id=storage_block_schema.id,
                block_type_id=storage_block_schema.block_type_id,
            ),
        )
        await session.commit()

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block.id
        )

        result = await session.execute(
            sa.select(db.BlockDocument).where(
                db.BlockDocument.is_default_storage_block_document.is_(True)
            )
        )
        default_blocks = result.scalars().unique().all()
        assert len(default_blocks) == 1
        assert default_blocks[0].id == storage_block.id

        await models.block_documents.set_default_storage_block_document(
            session=session, block_document_id=storage_block_2.id
        )

        result = await session.execute(
            sa.select(db.BlockDocument).where(
                db.BlockDocument.is_default_storage_block_document.is_(True)
            )
        )
        default_blocks = result.scalars().unique().all()
        assert len(default_blocks) == 1
        assert default_blocks[0].id == storage_block_2.id
