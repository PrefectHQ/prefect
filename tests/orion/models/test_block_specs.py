import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


@pytest.fixture
async def block_spec(session):
    model = await models.block_specs.create_block_spec(
        session=session,
        block_spec=schemas.core.BlockSpec(
            name="test-block-spec", version="1.0", type="notification"
        ),
    )
    await session.commit()
    return model


class TestCreateBlockSpec:
    async def test_create_block_spec(self, session):
        block_spec = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="1.0",
                type=None,
            ),
        )
        assert block_spec.name == "x"
        assert block_spec.version == "1.0"
        assert block_spec.type is None
        assert block_spec.fields == {}

        db_block_spec = await models.block_specs.read_block_spec(
            session=session, block_spec_id=block_spec.id
        )

        assert db_block_spec.name == block_spec.name
        assert db_block_spec.version == block_spec.version
        assert db_block_spec.type == block_spec.type
        assert db_block_spec.fields == block_spec.fields

    async def test_create_block_spec_unique_name_and_version(self, session):
        await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="1.0",
                type=None,
            ),
        )

        with pytest.raises(sa.exc.IntegrityError):
            await models.block_specs.create_block_spec(
                session=session,
                block_spec=schemas.core.BlockSpec(
                    name="x",
                    version="1.0",
                    type=None,
                ),
            )


class TestReadBlockSpecs:
    async def test_read_block_spec_by_name_and_version(self, session):
        block_spec = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="1.0",
                type=None,
            ),
        )

        db_block_spec = await models.block_specs.read_block_spec_by_name_and_version(
            session=session, name="x", version="1.0"
        )

        assert db_block_spec.id == block_spec.id
        assert db_block_spec.name == block_spec.name
        assert db_block_spec.version == block_spec.version
        assert db_block_spec.type == block_spec.type
        assert db_block_spec.fields == block_spec.fields

    async def test_read_block_specs_by_name(self, session):
        block_spec_1 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="1.0",
                type=None,
            ),
        )

        block_spec_2 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="y",
                version="1.0",
                type=None,
            ),
        )

        block_spec_3 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="2.0",
                type=None,
            ),
        )

        db_block_spec = await models.block_specs.read_block_specs(
            session=session, name="x"
        )

        assert len(db_block_spec) == 2
        assert db_block_spec[0].id == block_spec_1.id
        assert db_block_spec[0].version == block_spec_1.version
        assert db_block_spec[1].id == block_spec_3.id
        assert db_block_spec[1].version == block_spec_3.version

    async def test_read_block_specs_by_type(self, session):
        block_spec_1 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="1.0",
                type="abc",
            ),
        )

        block_spec_2 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="y",
                version="1.0",
                type="abc",
            ),
        )

        block_spec_3 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="2.0",
                type=None,
            ),
        )

        db_block_spec = await models.block_specs.read_block_specs(
            session=session, block_spec_type="abc"
        )

        assert len(db_block_spec) == 2
        assert db_block_spec[0].id == block_spec_1.id
        assert db_block_spec[1].id == block_spec_2.id

    async def test_read_block_specs_by_type_and_name(self, session):
        block_spec_1 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="1.0",
                type="abc",
            ),
        )

        block_spec_2 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="y",
                version="1.0",
                type="abc",
            ),
        )

        block_spec_3 = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="x",
                version="2.0",
                type=None,
            ),
        )

        db_block_spec = await models.block_specs.read_block_specs(
            session=session, block_spec_type="abc", name="x"
        )
        assert len(db_block_spec) == 1
        assert db_block_spec[0].id == block_spec_1.id

        db_block_spec = await models.block_specs.read_block_specs(
            session=session, block_spec_type="abc", name="z"
        )
        assert len(db_block_spec) == 0


class TestDeleteBlockSpec:
    async def test_delete_block_spec(self, session, block_spec):
        block_spec_id = block_spec.id
        assert await models.block_specs.delete_block_spec(
            session=session, block_spec_id=block_spec_id
        )
        assert not await models.block_specs.read_block_spec(
            session=session, block_spec_id=block_spec_id
        )

    async def test_delete_block_spec_fails_gracefully(self, session, block_spec):
        block_spec_id = block_spec.id
        assert await models.block_specs.delete_block_spec(
            session=session, block_spec_id=block_spec_id
        )
        assert not await models.block_specs.delete_block_spec(
            session=session, block_spec_id=block_spec_id
        )
