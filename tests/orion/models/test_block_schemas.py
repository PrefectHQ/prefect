from typing import Union

import pytest
import sqlalchemy as sa

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.models.block_schemas import read_block_schema_by_checksum

EMPTY_OBJECT_CHECKSUM = Block._calculate_schema_checksum({})


class TestCreateBlockSchema:
    async def test_create_block_schema(self, session, block_type_x):
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={
                    "title": "x",
                    "type": "object",
                    "properties": {
                        "access_key_id": {"title": "Access Key Id", "type": "string"},
                        "secret_access_key": {
                            "title": "Secret Access Key",
                            "type": "string",
                        },
                        "session_token": {"title": "Session Token", "type": "string"},
                    },
                    "block_type_name": "x",
                    "block_schema_references": {},
                },
                block_type_id=block_type_x.id,
                capabilities=["this block can test"],
            ),
        )
        assert block_schema.fields == {
            "title": "x",
            "type": "object",
            "properties": {
                "access_key_id": {"title": "Access Key Id", "type": "string"},
                "secret_access_key": {"title": "Secret Access Key", "type": "string"},
                "session_token": {"title": "Session Token", "type": "string"},
            },
            "block_type_name": "x",
            "block_schema_references": {},
        }
        assert (
            block_schema.checksum
            == "sha256:370cd74ce1fba0a96cf820775c744a32ab58f1f7c851f270c2040485878b8449"
        )
        assert block_schema.block_type_id == block_type_x.id

        db_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert db_block_schema.checksum == block_schema.checksum
        assert db_block_schema.fields == block_schema.fields
        assert db_block_schema.block_type_id == block_schema.block_type_id
        assert db_block_schema.capabilities == ["this block can test"]

    async def test_create_nested_block_schema(self, session, block_type_x):
        class Y(Block):
            a: str
            b: str

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y: Y
            z: str

        await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session, block_schema=X._to_block_schema()
        )

        nested_block_schema = await read_block_schema_by_checksum(
            session=session,
            checksum=Y._calculate_schema_checksum(),
        )
        assert nested_block_schema is not None
        assert nested_block_schema.fields == {
            "block_schema_references": {},
            "block_type_name": "Y",
            "properties": {
                "a": {"title": "A", "type": "string"},
                "b": {"title": "B", "type": "string"},
            },
            "required": ["a", "b"],
            "title": "Y",
            "type": "object",
        }
        assert nested_block_schema.fields == Y.schema()

    async def test_create_multiply_nested_block_schema(self, session, block_type_x):
        class A(Block):
            d: str
            e: str

        class Z(Block):
            a: A
            c: int

        class Y(Block):
            b: str
            c: int

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y: Y
            z: Z

        await models.block_types.create_block_type(
            session=session, block_type=A._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Z._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session, block_schema=X._to_block_schema()
        )

        block_schemas = await models.block_schemas.read_block_schemas(session=session)
        assert len(block_schemas) == 4

        nested_block_schema = await read_block_schema_by_checksum(
            session=session,
            checksum=A._calculate_schema_checksum(),
        )
        assert nested_block_schema is not None
        assert nested_block_schema.fields == {
            "block_schema_references": {},
            "block_type_name": "A",
            "properties": {
                "d": {"title": "D", "type": "string"},
                "e": {"title": "E", "type": "string"},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
        }
        assert nested_block_schema.fields == A.schema()

    async def test_create_nested_block_schema_with_multiply_used_blocks(self, session):
        class A(Block):
            d: str
            e: str

        class Z(Block):
            a: A
            c: int

        class Y(Block):
            a: A
            b: str
            c: int

        class X(Block):
            y: Y
            z: Z

        await models.block_types.create_block_type(
            session=session, block_type=A._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Z._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )
        block_type_x = await models.block_types.create_block_type(
            session=session, block_type=X._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(block_type_id=block_type_x.id),
        )

        block_schemas = await models.block_schemas.read_block_schemas(session=session)
        assert len(block_schemas) == 4

        nested_block_schema_a = await read_block_schema_by_checksum(
            session=session,
            checksum=A._calculate_schema_checksum(),
        )
        assert nested_block_schema_a is not None
        assert nested_block_schema_a.fields == {
            "block_schema_references": {},
            "block_type_name": "A",
            "properties": {
                "d": {"title": "D", "type": "string"},
                "e": {"title": "E", "type": "string"},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
        }
        assert nested_block_schema_a.fields == A.schema()

        nested_block_schema_z = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=Z._calculate_schema_checksum()
            )
        )
        assert nested_block_schema_z is not None
        assert nested_block_schema_z.fields == Z.schema()
        assert (
            Z.schema()["block_schema_references"]["a"]["block_schema_checksum"]
            == A._calculate_schema_checksum()
        )

        nested_block_schema_y = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=Y._calculate_schema_checksum()
            )
        )
        assert nested_block_schema_y is not None
        assert nested_block_schema_y.fields == Y.schema()
        assert (
            Y.schema()["block_schema_references"]["a"]["block_schema_checksum"]
            == A._calculate_schema_checksum()
        )

    async def test_create_block_schema_with_union(
        self, session, block_type_x, block_type_y, block_type_z
    ):
        class Z(Block):
            _block_type_id = block_type_z.id
            _block_type_name = block_type_z.name

            b: str

        class Y(Block):
            _block_type_id = block_type_y.id
            _block_type_name = block_type_y.name

            a: str

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y_or_z: Union[Y, Z]

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(),
        )

        assert block_schema.checksum == X._calculate_schema_checksum()
        assert block_schema.fields == X.schema()

    async def test_create_nested_block_schema(self, session, block_type_x):
        class Y(Block):
            a: str
            b: str

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y: Y
            z: str

        await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session, block_schema=X._to_block_schema()
        )

        nested_block_schema = await read_block_schema_by_checksum(
            session=session,
            checksum=Y._calculate_schema_checksum(),
        )
        assert nested_block_schema is not None
        assert nested_block_schema.fields == {
            "block_schema_references": {},
            "block_type_name": "Y",
            "properties": {
                "a": {"title": "A", "type": "string"},
                "b": {"title": "B", "type": "string"},
            },
            "required": ["a", "b"],
            "title": "Y",
            "type": "object",
        }
        assert nested_block_schema.fields == Y.schema()

    async def test_create_multiply_nested_block_schema(self, session, block_type_x):
        class A(Block):
            d: str
            e: str

        class Z(Block):
            a: A
            c: int

        class Y(Block):
            b: str
            c: int

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y: Y
            z: Z

        await models.block_types.create_block_type(
            session=session, block_type=A._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Z._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session, block_schema=X._to_block_schema()
        )

        block_schemas = await models.block_schemas.read_block_schemas(session=session)
        assert len(block_schemas) == 4

        nested_block_schema = await read_block_schema_by_checksum(
            session=session,
            checksum=A._calculate_schema_checksum(),
        )
        assert nested_block_schema is not None
        assert nested_block_schema.fields == {
            "block_schema_references": {},
            "block_type_name": "A",
            "properties": {
                "d": {"title": "D", "type": "string"},
                "e": {"title": "E", "type": "string"},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
        }
        assert nested_block_schema.fields == A.schema()

    async def test_create_nested_block_schema_with_multiply_used_blocks(self, session):
        class A(Block):
            d: str
            e: str

        class Z(Block):
            a: A
            c: int

        class Y(Block):
            a: A
            b: str
            c: int

        class X(Block):
            y: Y
            z: Z

        await models.block_types.create_block_type(
            session=session, block_type=A._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Z._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )
        block_type_x = await models.block_types.create_block_type(
            session=session, block_type=X._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(block_type_id=block_type_x.id),
        )

        block_schemas = await models.block_schemas.read_block_schemas(session=session)
        assert len(block_schemas) == 4

        nested_block_schema_a = await read_block_schema_by_checksum(
            session=session,
            checksum=A._calculate_schema_checksum(),
        )
        assert nested_block_schema_a is not None
        assert nested_block_schema_a.fields == {
            "block_schema_references": {},
            "block_type_name": "A",
            "properties": {
                "d": {"title": "D", "type": "string"},
                "e": {"title": "E", "type": "string"},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
        }
        assert nested_block_schema_a.fields == A.schema()

        nested_block_schema_z = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=Z._calculate_schema_checksum()
            )
        )
        assert nested_block_schema_z is not None
        assert nested_block_schema_z.fields == Z.schema()
        assert (
            Z.schema()["block_schema_references"]["a"]["block_schema_checksum"]
            == A._calculate_schema_checksum()
        )

        nested_block_schema_y = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=Y._calculate_schema_checksum()
            )
        )
        assert nested_block_schema_y is not None
        assert nested_block_schema_y.fields == Y.schema()
        assert (
            Y.schema()["block_schema_references"]["a"]["block_schema_checksum"]
            == A._calculate_schema_checksum()
        )

    async def test_create_block_schema_with_union(
        self, session, block_type_x, block_type_y, block_type_z
    ):
        class Z(Block):
            _block_type_id = block_type_z.id
            _block_type_name = block_type_z.name

            b: str

        class Y(Block):
            _block_type_id = block_type_y.id
            _block_type_name = block_type_y.name

            a: str

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y_or_z: Union[Y, Z]

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(),
        )

        assert block_schema.checksum == X._calculate_schema_checksum()
        assert block_schema.fields == X.schema()

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
    async def test_read_block_schema(self, session, nested_block_schema):
        db_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=nested_block_schema.id
        )

        assert db_block_schema.id == nested_block_schema.id
        assert db_block_schema.checksum == nested_block_schema.checksum
        assert db_block_schema.fields == nested_block_schema.fields
        assert db_block_schema.block_type_id == nested_block_schema.block_type_id

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

    async def test_read_all_block_schemas(self, session):
        class A(Block):
            d: str
            e: str

        class Z(Block):
            a: A
            c: int

        class Y(Block):
            b: str
            c: int

        class X(Block):
            y: Y
            z: Z

        await models.block_types.create_block_type(
            session=session, block_type=A._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Z._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )
        block_type_x = await models.block_types.create_block_type(
            session=session, block_type=X._to_block_type()
        )

        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(
                block_type_id=block_type_x.id,
            ),
        )

        await session.commit()

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session
        )

        assert len(db_block_schemas) == 4
        assert db_block_schemas[3].checksum == X._calculate_schema_checksum()
        assert db_block_schemas[2].checksum == Y._calculate_schema_checksum()
        assert db_block_schemas[1].checksum == Z._calculate_schema_checksum()
        assert db_block_schemas[0].checksum == A._calculate_schema_checksum()
        assert db_block_schemas[3].fields == X.schema()
        assert db_block_schemas[2].fields == Y.schema()
        assert db_block_schemas[1].fields == Z.schema()
        assert db_block_schemas[0].fields == A.schema()

    async def test_read_all_block_schemas_with_filters(self, session):
        class A(Block):
            d: str
            e: str

        class Z(Block):
            a: A
            c: int

        class Y(Block):
            b: str
            c: int

        class X(Block):
            y: Y
            z: Z

        await models.block_types.create_block_type(
            session=session, block_type=A._to_block_type()
        )
        await models.block_types.create_block_type(
            session=session, block_type=Z._to_block_type()
        )
        block_type_y = await models.block_types.create_block_type(
            session=session, block_type=Y._to_block_type()
        )
        block_type_x = await models.block_types.create_block_type(
            session=session, block_type=X._to_block_type()
        )

        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(
                block_type_id=block_type_x.id,
            ),
        )

        await session.commit()

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_type_id=dict(any_=[block_type_x.id])
            ),
        )

        assert len(db_block_schemas) == 1
        assert db_block_schemas[0].block_type_id == block_type_x.id

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_type_id=dict(any_=[block_type_x.id, block_type_y.id])
            ),
        )

        assert len(db_block_schemas) == 2
        assert db_block_schemas[0].block_type_id == block_type_y.id
        assert db_block_schemas[1].block_type_id == block_type_x.id

    async def test_read_block_schema_with_union(
        self, session, block_type_x, block_type_y, block_type_z
    ):
        class Z(Block):
            _block_type_id = block_type_z.id
            _block_type_name = block_type_z.name

            b: str

        class Y(Block):
            _block_type_id = block_type_y.id
            _block_type_name = block_type_y.name

            a: str

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y_or_z: Union[Y, Z]

        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(),
        )

        block_schema = await models.block_schemas.read_block_schema_by_checksum(
            session=session, checksum=X._calculate_schema_checksum()
        )

        assert block_schema.fields == X.schema()

    async def test_read_block_schema_with_union(
        self, session, block_type_x, block_type_y, block_type_z
    ):
        class Z(Block):
            _block_type_id = block_type_z.id
            _block_type_name = block_type_z.name

            b: str

        class Y(Block):
            _block_type_id = block_type_y.id
            _block_type_name = block_type_y.name

            a: str

        class X(Block):
            _block_type_id = block_type_x.id
            _block_type_name = block_type_x.name

            y_or_z: Union[Y, Z]

        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=X._to_block_schema(),
        )

        block_schema = await models.block_schemas.read_block_schema_by_checksum(
            session=session, checksum=X._calculate_schema_checksum()
        )

        assert block_schema.fields == X.schema()


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
