import hashlib
import json

import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.utilities.hashing import hash_objects

EMPTY_OBJECT_CHECKSUM = f"sha256:{hash_objects({}, hash_algo=hashlib.sha256)}"


class TestCreateBlockSchema:
    async def test_create_block_schema(self, session, block_type_x):
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={},
                block_type_id=block_type_x.id,
                capabilities=["this block can test"],
            ),
        )
        assert block_schema.fields == {}
        assert block_schema.checksum == EMPTY_OBJECT_CHECKSUM
        assert block_schema.block_type_id == block_type_x.id

        db_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert db_block_schema.checksum == block_schema.checksum
        assert db_block_schema.fields == block_schema.fields
        assert db_block_schema.block_type_id == block_schema.block_type_id
        assert db_block_schema.capabilities == ["this block can test"]

    async def test_create_block_schema_unique_checksum(self, session, block_type_x):
        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.block_schemas.create_block_schema(
                session=session,
                block_schema=schemas.actions.BlockSchemaCreate(
                    fields={},
                    block_type_id=block_type_x.id,
                ),
            )


class TestReadBlockSchemas:
    async def test_read_block_schema_by_checksum(self, session, block_type_x):
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        db_block_schema = await models.block_schemas.read_block_schema_by_checksum(
            session=session, checksum=EMPTY_OBJECT_CHECKSUM
        )

        assert db_block_schema.id == block_schema.id
        assert db_block_schema.checksum == block_schema.checksum
        assert db_block_schema.fields == block_schema.fields
        assert db_block_schema.block_type_id == block_schema.block_type_id


class TestDeleteBlockSchema:
    async def test_delete_block_schema(self, session, block_schema):
        block_schema_id = block_schema.id
        assert await models.block_schemas.delete_block_schema(
            session=session, block_schema_id=block_schema_id
        )
        assert not await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema_id
        )

    async def test_delete_block_schema_fails_gracefully(self, session, block_schema):
        block_schema_id = block_schema.id
        assert await models.block_schemas.delete_block_schema(
            session=session, block_schema_id=block_schema_id
        )
        assert not await models.block_schemas.delete_block_schema(
            session=session, block_schema_id=block_schema_id
        )
