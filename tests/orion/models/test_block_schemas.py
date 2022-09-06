import warnings
from typing import List, Union

import pytest
import sqlalchemy as sa
from pydantic import BaseModel

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.models.block_schemas import read_block_schema_by_checksum
from prefect.orion.schemas.filters import BlockSchemaFilter
from prefect.utilities.collections import AutoEnum

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
                    "block_type_slug": "x",
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
            "block_type_slug": "x",
            "block_schema_references": {},
        }
        assert (
            block_schema.checksum
            == "sha256:4448d5cf2ddb989f7fde8b2c36ec89527ca30e0e8ef041eed8bd15c11fe6cfee"
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
            "block_type_slug": "y",
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
            "block_type_slug": "a",
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
            "block_type_slug": "a",
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
            "block_type_slug": "y",
            "properties": {
                "a": {"title": "A", "type": "string"},
                "b": {"title": "B", "type": "string"},
            },
            "required": ["a", "b"],
            "title": "Y",
            "type": "object",
            "secret_fields": [],
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
            "block_type_slug": "a",
            "properties": {
                "d": {"title": "D", "type": "string"},
                "e": {"title": "E", "type": "string"},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
            "secret_fields": [],
        }
        assert nested_block_schema.fields == A.schema()

    async def test_create_nested_block_schema_with_multiply_used_blocks(self, session):
        warnings.filterwarnings("ignore", category=UserWarning)

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
            "block_type_slug": "a",
            "properties": {
                "d": {"title": "D", "type": "string"},
                "e": {"title": "E", "type": "string"},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
            "secret_fields": [],
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

    async def test_create_block_schema_is_idempotent(self, session, block_type_x):
        first_create_response = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        # Should not raise
        second_create_response = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        # Should not raise
        third_create_response = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={},
                block_type_id=block_type_x.id,
            ),
        )

        assert (
            first_create_response.id
            == second_create_response.id
            == third_create_response.id
        )

    async def test_create_block_schema_is_idempotent_for_nested_blocks(self, session):
        class Child(Block):
            age: int

        class Parent(Block):
            child: Child

        parent_block_type = await models.block_types.create_block_type(
            session=session, block_type=Parent._to_block_type()
        )
        child_block_type = await models.block_types.create_block_type(
            session=session, block_type=Child._to_block_type()
        )

        parent_create_response = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=Parent._to_block_schema(block_type_id=parent_block_type.id),
        )

        # Should not raise
        child_create_response = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=Child._to_block_schema(block_type_id=child_block_type.id),
        )

        assert (
            parent_create_response.fields["block_schema_references"]["child"][
                "block_schema_checksum"
            ]
            == child_create_response.checksum
        )


class TestReadBlockSchemas:
    @pytest.fixture
    async def block_schemas_with_capabilities(self, session):
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

        return block_schema_duck, block_schema_bird, block_schema_cat

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

    async def test_read_block_schema_by_checksum_with_version(
        self, session, client, block_type_x
    ):
        # Create two block schemas with the same checksum, but different versions
        block_schema_0 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={}, block_type_id=block_type_x.id, version="1.0.1"
            ),
        )

        block_schema_1 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={}, block_type_id=block_type_x.id, version="1.1.0"
            ),
        )

        assert block_schema_0.checksum == block_schema_1.checksum

        # Read first version with version query parameter
        read_block_schema = await models.block_schemas.read_block_schema_by_checksum(
            session=session, checksum=block_schema_0.checksum, version="1.0.1"
        )

        assert read_block_schema.id == block_schema_0.id

        # Read second version with version
        read_block_schema = await models.block_schemas.read_block_schema_by_checksum(
            session=session, checksum=block_schema_1.checksum, version="1.1.0"
        )

        assert read_block_schema.id == block_schema_1.id

        # Read without version. Should return most recently created block schema.
        read_block_schema = await models.block_schemas.read_block_schema_by_checksum(
            session=session, checksum=block_schema_0.checksum
        )

        assert read_block_schema.id == block_schema_1.id

    async def test_read_block_schema_does_not_hardcode_references(
        self, session, db, block_type_x
    ):
        block_schema = await models.block_schemas.create_block_schema(
            override=True,
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={
                    "title": "JSON",
                    "description": "A block that represents JSON",
                    "type": "object",
                    "properties": {
                        "value": {
                            "title": "Value",
                            "description": "A JSON-compatible value",
                        }
                    },
                    "required": ["value"],
                    "block_type_slug": "json",
                    "secret_fields": [],
                    "block_schema_references": {},
                },
                block_type_id=block_type_x.id,
            ),
        )
        before_read = (
            await session.execute(
                sa.select(db.BlockSchema).where(db.BlockSchema.id == block_schema.id)
            )
        ).scalar()
        assert before_read.fields.get("block_schema_references") is None
        read_result = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        await session.commit()
        after_read = (
            await session.execute(
                sa.select(db.BlockSchema).where(db.BlockSchema.id == block_schema.id)
            )
        ).scalar()
        assert after_read.fields.get("block_schema_references") is None

    @pytest.fixture
    async def nested_schemas(self, session):
        # Ignore warnings caused by Block reuse in fixture
        warnings.filterwarnings("ignore", category=UserWarning)

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
            _block_schema_version = "1.1.0"

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

        return (A, X, Y, Z, block_type_x, block_type_y)

    async def test_read_all_block_schemas(self, session, nested_schemas):
        A, X, Y, Z, block_type_x, block_type_y = nested_schemas

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session
        )

        assert len(db_block_schemas) == 4
        assert db_block_schemas[0].checksum == A._calculate_schema_checksum()
        assert db_block_schemas[1].checksum == Z._calculate_schema_checksum()
        assert db_block_schemas[2].checksum == Y._calculate_schema_checksum()
        assert db_block_schemas[3].checksum == X._calculate_schema_checksum()
        assert db_block_schemas[0].fields == A.schema()
        assert db_block_schemas[1].fields == Z.schema()
        assert db_block_schemas[2].fields == Y.schema()
        assert db_block_schemas[3].fields == X.schema()

    async def test_read_all_block_schemas_with_limit(self, session, nested_schemas):
        A, X, Y, Z, block_type_x, block_type_y = nested_schemas

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session, limit=2
        )

        assert len(db_block_schemas) == 2
        assert db_block_schemas[0].checksum == A._calculate_schema_checksum()
        assert db_block_schemas[1].checksum == Z._calculate_schema_checksum()
        assert db_block_schemas[0].fields == A.schema()
        assert db_block_schemas[1].fields == Z.schema()

    async def test_read_all_block_schemas_with_limit_and_offset(
        self, session, nested_schemas
    ):
        A, X, Y, Z, block_type_x, block_type_y = nested_schemas

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session, limit=2, offset=2
        )

        assert len(db_block_schemas) == 2
        assert db_block_schemas[0].checksum == Y._calculate_schema_checksum()
        assert db_block_schemas[1].checksum == X._calculate_schema_checksum()
        assert db_block_schemas[0].fields == Y.schema()
        assert db_block_schemas[1].fields == X.schema()

    async def test_read_all_block_schemas_with_filters(self, session, nested_schemas):
        A, X, Y, Z, block_type_x, block_type_y = nested_schemas

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

    async def test_read_all_block_schemas_with_block_type_and_version_filters(
        self, session, nested_schemas
    ):
        A, X, Y, Z, block_type_x, block_type_y = nested_schemas

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_type_id=dict(any_=[block_type_x.id]),
                version=dict(any_=[X._block_schema_version]),
            ),
        )

        assert len(db_block_schemas) == 1
        assert db_block_schemas[0].block_type_id == block_type_x.id

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=schemas.filters.BlockSchemaFilter(
                block_type_id=dict(any_=[block_type_x.id]), version=dict(any_=["1.1.1"])
            ),
        )

        assert len(db_block_schemas) == 0

    async def test_read_block_schemas_with_capabilities_filter(
        self, session, block_schemas_with_capabilities
    ):
        fly_and_swim_block_schemas = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=BlockSchemaFilter(
                block_capabilities=dict(all_=["fly", "swim"])
            ),
        )
        assert len(fly_and_swim_block_schemas) == 1
        assert [b.id for b in fly_and_swim_block_schemas] == [
            block_schemas_with_capabilities[0].id
        ]

        fly_block_schemas = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=BlockSchemaFilter(
                block_capabilities=dict(all_=["fly"])
            ),
        )
        assert len(fly_block_schemas) == 2
        assert [b.id for b in fly_block_schemas] == [
            block_schemas_with_capabilities[1].id,
            block_schemas_with_capabilities[0].id,
        ]

        swim_block_schemas = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=BlockSchemaFilter(
                block_capabilities=dict(all_=["swim"])
            ),
        )
        assert len(swim_block_schemas) == 1
        assert [b.id for b in swim_block_schemas] == [
            block_schemas_with_capabilities[0].id
        ]

    @pytest.mark.flaky(
        max_runs=3
    )  # Order of block schema references sometimes doesn't match
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

    async def test_read_block_schemas_with_id_list(self, session, nested_schemas):
        A, X, Y, Z, block_type_x, block_type_y = nested_schemas

        a_id = (
            await read_block_schema_by_checksum(
                session=session, checksum=A._calculate_schema_checksum()
            )
        ).id
        y_id = (
            await read_block_schema_by_checksum(
                session=session, checksum=Y._calculate_schema_checksum()
            )
        ).id

        result = await models.block_schemas.read_block_schemas(
            session=session,
            block_schema_filter=BlockSchemaFilter(id=dict(any_=[a_id, y_id])),
        )

        assert len(result) == 2
        assert [a_id, y_id] == [b.id for b in result]

    async def test_read_block_with_non_block_object_attributes(self, session):
        class NotABlock(BaseModel):
            alias: str

        class AlsoNotABlock(BaseModel):
            pseudonym: str
            child: NotABlock

        class IsABlock(Block):
            size: int
            contents: AlsoNotABlock

        block_type = await models.block_types.create_block_type(
            session=session, block_type=IsABlock._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=IsABlock._to_block_schema(block_type_id=block_type.id),
        )

        assert block_schema.fields == IsABlock.schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert read_block_schema.fields == IsABlock.schema()

    async def test_read_block_with_enum_attribute(self, session):
        class Fruit(AutoEnum):
            APPLE = AutoEnum.auto()
            BANANA = AutoEnum.auto()
            ORANGE = AutoEnum.auto()

        class IsABlock(Block):
            size: int
            contents: Fruit

        block_type = await models.block_types.create_block_type(
            session=session, block_type=IsABlock._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=IsABlock._to_block_schema(block_type_id=block_type.id),
        )

        assert block_schema.fields == IsABlock.schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert read_block_schema.fields == IsABlock.schema()

    async def test_read_block_with_non_block_union_attribute(self, session):
        class NotABlock(BaseModel):
            alias: str

        class AlsoNotABlock(BaseModel):
            pseudonym: str

        class IsABlock(Block):
            size: int
            contents: Union[NotABlock, AlsoNotABlock]

        block_type = await models.block_types.create_block_type(
            session=session, block_type=IsABlock._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=IsABlock._to_block_schema(block_type_id=block_type.id),
        )

        assert block_schema.fields == IsABlock.schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        assert read_block_schema.fields == IsABlock.schema()

    async def test_read_block_with_non_block_list_attribute(self, session):
        class NotABlock(BaseModel):
            alias: str

        class IsABlock(Block):
            size: int
            contents: List[NotABlock]

        block_type = await models.block_types.create_block_type(
            session=session, block_type=IsABlock._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=IsABlock._to_block_schema(block_type_id=block_type.id),
        )

        assert block_schema.fields == IsABlock.schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        assert read_block_schema.fields == IsABlock.schema()

    async def test_read_block_with_both_block_and_non_block_attributes(self, session):
        class NotABlock(BaseModel):
            alias: str

        class IsABlock(Block):
            size: int

        class IsAlsoABlock(Block):
            size: float
            contents: IsABlock
            config: NotABlock

        await models.block_types.create_block_type(
            session=session, block_type=IsABlock._to_block_type()
        )

        block_type = await models.block_types.create_block_type(
            session=session, block_type=IsAlsoABlock._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=IsAlsoABlock._to_block_schema(block_type_id=block_type.id),
        )

        assert block_schema.fields == IsAlsoABlock.schema()
        assert block_schema.checksum == IsAlsoABlock._calculate_schema_checksum()

        read_parent_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        assert read_parent_block_schema.fields == IsAlsoABlock.schema()

        read_child_block_schema = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=IsABlock._calculate_schema_checksum()
            )
        )
        assert read_child_block_schema.fields == IsABlock.schema()

    async def test_read_block_schema_with_list_block_attribute(self, session):
        class Child(Block):
            age: float

        class Parent(Block):
            age: int
            children: List[Child]

        await models.block_types.create_block_type(
            session=session, block_type=Child._to_block_type()
        )

        block_type = await models.block_types.create_block_type(
            session=session, block_type=Parent._to_block_type()
        )

        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=Parent._to_block_schema(block_type_id=block_type.id),
        )

        assert block_schema.fields == Parent.schema()
        assert block_schema.checksum == Parent._calculate_schema_checksum()
        assert block_schema.fields["block_schema_references"] == {
            "children": {
                "block_type_slug": "child",
                "block_schema_checksum": Child._calculate_schema_checksum(),
            }
        }

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        assert read_block_schema.fields == Parent.schema()


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


@pytest.fixture
async def block_schemas_with_capabilities(session):
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

    block_type_a = await models.block_types.create_block_type(
        session=session, block_type=Duck._to_block_type()
    )
    block_schema_a = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=Duck._to_block_schema(block_type_id=block_type_a.id),
    )
    block_type_b = await models.block_types.create_block_type(
        session=session, block_type=Bird._to_block_type()
    )
    block_schema_b = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=Bird._to_block_schema(block_type_id=block_type_b.id),
    )
    block_type_c = await models.block_types.create_block_type(
        session=session, block_type=Cat._to_block_type()
    )
    block_schema_c = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=Cat._to_block_schema(block_type_id=block_type_c.id),
    )


class TestListAvailableBlockCapabilities:
    async def test_list_available_block_capabilities(
        self, session, block_schemas_with_capabilities
    ):
        assert sorted(
            await models.block_schemas.read_available_block_capabilities(
                session=session
            )
        ) == sorted(["run", "fly", "swim"])

    async def test_list_available_block_capabilities_with_no_schemas(self, session):
        assert (
            await models.block_schemas.read_available_block_capabilities(
                session=session
            )
            == []
        )
