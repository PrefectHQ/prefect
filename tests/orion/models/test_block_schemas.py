import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


@pytest.fixture
async def block_schema(session):
    model = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.core.BlockSchema(
            name="test-block-spec", version="1.0", type="notification"
        ),
    )
    await session.commit()
    return model


class TestCreateBlockSchema:
    async def test_create_block_schema(self, session):
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="1.0",
                type=None,
            ),
        )
        assert block_schema.name == "x"
        assert block_schema.version == "1.0"
        assert block_schema.type is None
        assert block_schema.fields == {}

        db_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert db_block_schema.name == block_schema.name
        assert db_block_schema.version == block_schema.version
        assert db_block_schema.type == block_schema.type
        assert db_block_schema.fields == block_schema.fields

    async def test_create_block_schema_unique_name_and_version(self, session):
        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="1.0",
                type=None,
            ),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.block_schemas.create_block_schema(
                session=session,
                block_schema=schemas.core.BlockSchema(
                    name="x",
                    version="1.0",
                    type=None,
                ),
            )


class TestReadBlockSchemas:
    async def test_read_block_schema_by_name_and_version(self, session):
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="1.0",
                type=None,
            ),
        )

        db_block_schema = (
            await models.block_schemas.read_block_schema_by_name_and_version(
                session=session, name="x", version="1.0"
            )
        )

        assert db_block_schema.id == block_schema.id
        assert db_block_schema.name == block_schema.name
        assert db_block_schema.version == block_schema.version
        assert db_block_schema.type == block_schema.type
        assert db_block_schema.fields == block_schema.fields

    async def test_read_block_schemas_by_name(self, session):
        block_schema_1 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="1.0",
                type=None,
            ),
        )

        block_schema_2 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="y",
                version="1.0",
                type=None,
            ),
        )

        block_schema_3 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="2.0",
                type=None,
            ),
        )

        db_block_schema = await models.block_schemas.read_block_schemas(
            session=session, name="x"
        )

        assert len(db_block_schema) == 2
        assert db_block_schema[0].id == block_schema_1.id
        assert db_block_schema[0].version == block_schema_1.version
        assert db_block_schema[1].id == block_schema_3.id
        assert db_block_schema[1].version == block_schema_3.version

    async def test_read_block_schemas_by_type(self, session):
        block_schema_1 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="1.0",
                type="abc",
            ),
        )

        block_schema_2 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="y",
                version="1.0",
                type="abc",
            ),
        )

        block_schema_3 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="2.0",
                type=None,
            ),
        )

        db_block_schema = await models.block_schemas.read_block_schemas(
            session=session, block_schema_type="abc"
        )

        assert len(db_block_schema) == 2
        assert db_block_schema[0].id == block_schema_1.id
        assert db_block_schema[1].id == block_schema_2.id

    async def test_read_block_schemas_by_type_and_name(self, session):
        block_schema_1 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="1.0",
                type="abc",
            ),
        )

        block_schema_2 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="y",
                version="1.0",
                type="abc",
            ),
        )

        block_schema_3 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.core.BlockSchema(
                name="x",
                version="2.0",
                type=None,
            ),
        )

        db_block_schema = await models.block_schemas.read_block_schemas(
            session=session, block_schema_type="abc", name="x"
        )
        assert len(db_block_schema) == 1
        assert db_block_schema[0].id == block_schema_1.id

        db_block_schema = await models.block_schemas.read_block_schemas(
            session=session, block_schema_type="abc", name="z"
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
