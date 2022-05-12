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
                type=None,
                fields={},
                block_type_id=block_type_x.id,
            ),
        )
        assert block_schema.type is None
        assert block_schema.fields == {}
        assert block_schema.checksum == EMPTY_OBJECT_CHECKSUM
        assert block_schema.block_type_id == block_type_x.id

        db_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert db_block_schema.checksum == block_schema.checksum
        assert db_block_schema.type == block_schema.type
        assert db_block_schema.fields == block_schema.fields
        assert db_block_schema.block_type_id == block_schema.block_type_id

    async def test_create_block_schema_unique_checksum(self, session, block_type_x):
        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type=None,
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.block_schemas.create_block_schema(
                session=session,
                block_schema=schemas.actions.BlockSchemaCreate(
                    type=None,
                    fields={},
                    block_type_id=block_type_x.id,
                ),
            )


class TestReadBlockSchemas:
    async def test_read_block_schema_by_checksum(self, session, block_type_x):
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type=None,
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        db_block_schema = await models.block_schemas.read_block_schema_by_checksum(
            session=session, checksum=EMPTY_OBJECT_CHECKSUM
        )

        assert db_block_schema.id == block_schema.id
        assert db_block_schema.checksum == block_schema.checksum
        assert db_block_schema.type == block_schema.type
        assert db_block_schema.fields == block_schema.fields
        assert db_block_schema.block_type_id == block_schema.block_type_id

    async def test_read_block_schemas_by_type(self, session, block_type_x):
        block_schema_1 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type="abc",
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        block_schema_2 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type="abc",
                fields={"x": {"type": "int"}},
                block_type_id=block_type_x.id,
            ),
        )

        block_schema_3 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type=None,
                fields={"y": {"type": "int"}},
                block_type_id=block_type_x.id,
            ),
        )

        db_block_schema = await models.block_schemas.read_block_schemas(
            session=session, block_schema_type="abc"
        )

        assert len(db_block_schema) == 2
        assert db_block_schema[0].id == block_schema_1.id
        assert db_block_schema[1].id == block_schema_2.id

    async def test_read_block_schemas_by_type_and_name(
        self, session, block_type_x, block_type_y, block_type_z
    ):
        block_schema_1 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type="abc",
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        block_schema_2 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type="abc",
                fields={"x": {"type": "int"}},
                block_type_id=block_type_y.id,
            ),
        )

        block_schema_3 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                type=None,
                fields={"y": {"type": "int"}},
                block_type_id=block_type_x.id,
            ),
        )

        db_block_schema = await models.block_schemas.read_block_schemas(
            session=session, block_schema_type="abc", block_type_id=block_type_x.id
        )
        assert len(db_block_schema) == 1
        assert db_block_schema[0].id == block_schema_1.id

        db_block_schema = await models.block_schemas.read_block_schemas(
            session=session, block_schema_type="abc", block_type_id=block_type_z.id
        )
        assert len(db_block_schema) == 0


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
