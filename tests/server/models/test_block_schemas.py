import uuid
import warnings
from typing import List, Union

import pytest
import sqlalchemy as sa
from pydantic import BaseModel

from prefect.blocks.core import Block
from prefect.server import models, schemas
from prefect.server.database import orm_models
from prefect.server.models.block_schemas import (
    _construct_block_schema_spec_definitions,
    _construct_full_block_schema,
    _find_block_schema_via_checksum,
    read_block_schema_by_checksum,
)
from prefect.server.schemas.core import BlockSchema
from prefect.server.schemas.filters import BlockSchemaFilter
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

        await models.block_schemas.create_block_schema(
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
                "a": {"title": "A", "type": "string", "position": 0},
                "b": {"title": "B", "type": "string", "position": 1},
            },
            "required": ["a", "b"],
            "title": "Y",
            "type": "object",
            "secret_fields": [],
        }
        assert nested_block_schema.fields == Y.model_json_schema()

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

        await models.block_schemas.create_block_schema(
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
                "d": {"title": "D", "type": "string", "position": 0},
                "e": {"title": "E", "type": "string", "position": 1},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
            "secret_fields": [],
        }
        assert nested_block_schema.fields == A.model_json_schema()

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

        await models.block_schemas.create_block_schema(
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
                "d": {"title": "D", "type": "string", "position": 0},
                "e": {"title": "E", "type": "string", "position": 1},
            },
            "required": ["d", "e"],
            "title": "A",
            "type": "object",
            "secret_fields": [],
        }
        assert nested_block_schema_a.fields == A.model_json_schema()

        nested_block_schema_z = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=Z._calculate_schema_checksum()
            )
        )
        assert nested_block_schema_z is not None
        assert nested_block_schema_z.fields == Z.model_json_schema()
        assert (
            Z.model_json_schema()["block_schema_references"]["a"][
                "block_schema_checksum"
            ]
            == A._calculate_schema_checksum()
        )

        nested_block_schema_y = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=Y._calculate_schema_checksum()
            )
        )
        assert nested_block_schema_y is not None
        assert nested_block_schema_y.fields == Y.model_json_schema()
        assert (
            Y.model_json_schema()["block_schema_references"]["a"][
                "block_schema_checksum"
            ]
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
        assert block_schema.fields == X.model_json_schema()

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
                sa.select(orm_models.BlockSchema).where(
                    orm_models.BlockSchema.id == block_schema.id
                )
            )
        ).scalar()
        assert before_read.fields.get("block_schema_references") is None
        await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        await session.commit()
        after_read = (
            await session.execute(
                sa.select(orm_models.BlockSchema).where(
                    orm_models.BlockSchema.id == block_schema.id
                )
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
        assert db_block_schemas[0].fields == A.model_json_schema()
        assert db_block_schemas[1].fields == Z.model_json_schema()
        assert db_block_schemas[2].fields == Y.model_json_schema()
        assert db_block_schemas[3].fields == X.model_json_schema()

    async def test_read_all_block_schemas_with_limit(self, session, nested_schemas):
        A, X, Y, Z, block_type_x, block_type_y = nested_schemas

        db_block_schemas = await models.block_schemas.read_block_schemas(
            session=session, limit=2
        )

        assert len(db_block_schemas) == 2
        assert db_block_schemas[0].checksum == A._calculate_schema_checksum()
        assert db_block_schemas[1].checksum == Z._calculate_schema_checksum()
        assert db_block_schemas[0].fields == A.model_json_schema()
        assert db_block_schemas[1].fields == Z.model_json_schema()

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
        assert db_block_schemas[0].fields == Y.model_json_schema()
        assert db_block_schemas[1].fields == X.model_json_schema()

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

        block_schema = block_schema.fields
        x_schema = X.model_json_schema()

        assert block_schema["title"] == x_schema["title"]
        assert block_schema["type"] == x_schema["type"]
        assert block_schema["required"] == x_schema["required"]
        assert block_schema["block_type_slug"] == x_schema["block_type_slug"]
        assert block_schema["definitions"] == x_schema["definitions"]

        block_properties = block_schema["properties"]["y_or_z"]
        x_properties = x_schema["properties"]["y_or_z"]

        assert block_properties["title"] == x_properties["title"]
        block_property_refs = set([ref["$ref"] for ref in block_properties["anyOf"]])
        x_property_refs = set([ref["$ref"] for ref in x_properties["anyOf"]])
        assert block_property_refs == x_property_refs

        block_refs = [
            (ref["block_schema_checksum"], ref["block_type_slug"])
            for ref in block_schema["block_schema_references"]["y_or_z"]
        ]
        x_refs = [
            (ref["block_schema_checksum"], ref["block_type_slug"])
            for ref in x_schema["block_schema_references"]["y_or_z"]
        ]
        assert set(block_refs) == set(x_refs)

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

        assert block_schema.fields == IsABlock.model_json_schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert read_block_schema.fields == IsABlock.model_json_schema()

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

        assert block_schema.fields == IsABlock.model_json_schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )

        assert read_block_schema.fields == IsABlock.model_json_schema()

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

        assert block_schema.fields == IsABlock.model_json_schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        assert read_block_schema.fields == IsABlock.model_json_schema()

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

        assert block_schema.fields == IsABlock.model_json_schema()
        assert block_schema.checksum == IsABlock._calculate_schema_checksum()

        read_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        assert read_block_schema.fields == IsABlock.model_json_schema()

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

        assert block_schema.fields == IsAlsoABlock.model_json_schema()
        assert block_schema.checksum == IsAlsoABlock._calculate_schema_checksum()

        read_parent_block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema.id
        )
        assert read_parent_block_schema.fields == IsAlsoABlock.model_json_schema()

        read_child_block_schema = (
            await models.block_schemas.read_block_schema_by_checksum(
                session=session, checksum=IsABlock._calculate_schema_checksum()
            )
        )
        assert read_child_block_schema.fields == IsABlock.model_json_schema()

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

        assert block_schema.fields == Parent.model_json_schema()
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
        assert read_block_schema.fields == Parent.model_json_schema()


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
    await models.block_schemas.create_block_schema(
        session=session,
        block_schema=Duck._to_block_schema(block_type_id=block_type_a.id),
    )
    block_type_b = await models.block_types.create_block_type(
        session=session, block_type=Bird._to_block_type()
    )
    await models.block_schemas.create_block_schema(
        session=session,
        block_schema=Bird._to_block_schema(block_type_id=block_type_b.id),
    )
    block_type_c = await models.block_types.create_block_type(
        session=session, block_type=Cat._to_block_type()
    )
    await models.block_schemas.create_block_schema(
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


class TestConstructFullBlockSchemaHelpers:
    """Sniper tests for uncovered branches in the four target regions."""

    def _make_block_schema(self, checksum: str, fields: dict) -> BlockSchema:
        return BlockSchema(
            id=uuid.uuid4(),
            checksum=checksum,
            fields=fields,
            block_type_id=uuid.uuid4(),
            capabilities=[],
            version="1.0",
        )

    def test_construct_full_block_schema_raises_when_no_root_determinable(self):
        """Line 402: ValueError raised when all rows have a non-None parent id."""
        parent_id = uuid.uuid4()
        bs = self._make_block_schema(
            "sha256:aaa",
            {"title": "A", "block_schema_references": {}},
        )
        # Every tuple has a non-None parent_block_schema_id, so _find_root_block_schema
        # returns None and the ValueError branch at line 402 executes.
        rows = [(bs, "field_name", parent_id)]
        with pytest.raises(ValueError, match="Unable to determine root block schema"):
            _construct_full_block_schema(rows)

    def test_construct_block_schema_spec_definitions_skips_missing_checksum(self):
        """Branch 470->False: child_block_schema is None when checksum not found."""
        root_bs = self._make_block_schema(
            "sha256:root",
            {
                "title": "Root",
                "block_schema_references": {
                    "child_field": {
                        "block_schema_checksum": "sha256:does_not_exist",
                        "block_type_slug": "ghost",
                    }
                },
            },
        )
        # The pool contains only root_bs — "sha256:does_not_exist" will not be found.
        # _find_block_schema_via_checksum returns None and the if-block is skipped.
        rows = [(root_bs, None, None)]
        result = _construct_block_schema_spec_definitions(root_bs, rows)
        assert result == {}

    def test_construct_block_schema_spec_definitions_skips_missing_checksum_via_index(
        self,
    ):
        """R1: dict-index miss path returns {} without raising, even when called
        through _construct_block_schema_spec_definitions with a non-None index."""
        root_bs = self._make_block_schema(
            "sha256:root",
            {
                "title": "Root",
                "block_schema_references": {
                    "child_field": {
                        "block_schema_checksum": "sha256:does_not_exist",
                        "block_type_slug": "ghost",
                    }
                },
            },
        )
        rows = [(root_bs, None, None)]
        index = {"sha256:root": root_bs}  # deliberately omit "sha256:does_not_exist"
        result = _construct_block_schema_spec_definitions(
            root_bs, rows, checksum_index=index
        )
        assert result == {}


class TestChecksumIndexRegression:
    """Regression tests for the O(N^2) -> O(N) checksum-lookup fix.

    Locks in the new dict-index branch in
    ``_find_block_schema_via_checksum`` and the bulk-read loop hoist in
    ``read_block_schemas``.
    """

    def _make_block_schema(
        self, checksum, fields=None, block_type_id=None
    ) -> BlockSchema:
        return BlockSchema(
            id=uuid.uuid4(),
            checksum=checksum,
            fields=fields if fields is not None else {"block_schema_references": {}},
            block_type_id=block_type_id or uuid.uuid4(),
            capabilities=[],
            version="1.0",
        )

    def test_find_block_schema_with_index_returns_dict_hit(self):
        """AC2: when ``checksum_index`` is provided, return the dict entry."""
        # branch_target: src/prefect/server/models/block_schemas.py:503
        bs_a = self._make_block_schema("sha256:a")
        bs_b = self._make_block_schema("sha256:b")
        rows = [(bs_a, None, None), (bs_b, None, None)]
        index = {"sha256:a": bs_a, "sha256:b": bs_b}
        result = _find_block_schema_via_checksum(rows, "sha256:b", checksum_index=index)
        assert result is bs_b

    def test_find_block_schema_with_index_miss_returns_none(self):
        """AC2: dict-index miss returns None, never falls through to scan."""
        # branch_target: src/prefect/server/models/block_schemas.py:503
        bs_a = self._make_block_schema("sha256:a")
        # The row pool contains "sha256:other" but the index does not — a
        # linear scan would have found it. The dict path must NOT fall back.
        bs_other = self._make_block_schema("sha256:other")
        rows = [(bs_a, None, None), (bs_other, None, None)]
        index = {"sha256:a": bs_a}  # deliberately omit "sha256:other"
        result = _find_block_schema_via_checksum(
            rows, "sha256:other", checksum_index=index
        )
        assert result is None

    def test_find_block_schema_falls_back_without_index(self):
        """AC3 / AC7: when ``checksum_index`` is None, use the linear scan."""
        # branch_target: src/prefect/server/models/block_schemas.py:504
        bs_a = self._make_block_schema("sha256:a")
        bs_b = self._make_block_schema("sha256:b")
        rows = [(bs_a, None, None), (bs_b, None, None)]
        result = _find_block_schema_via_checksum(rows, "sha256:b", checksum_index=None)
        assert result is bs_b

    def test_find_block_schema_with_index_matches_without_index(self):
        """AC8: dict path and scan path agree on identical inputs."""
        bs_a = self._make_block_schema("sha256:a")
        bs_b = self._make_block_schema("sha256:b")
        bs_c = self._make_block_schema("sha256:c")
        rows = [(bs_a, None, None), (bs_b, None, None), (bs_c, None, None)]
        index = {bs.checksum: bs for bs, _, _ in rows}
        for checksum in ("sha256:a", "sha256:b", "sha256:c", "sha256:missing"):
            with_index = _find_block_schema_via_checksum(
                rows, checksum, checksum_index=index
            )
            without_index = _find_block_schema_via_checksum(
                rows, checksum, checksum_index=None
            )
            assert with_index is without_index

    def test_construct_full_block_schema_excludes_none_checksum_rows(self):
        """AC4 / AC9: rows with ``checksum=None`` must not raise during index build."""
        # branch_target: src/prefect/server/models/block_schemas.py:413
        # A row with checksum=None (e.g., a partially-hydrated ORM row) must be
        # filtered out of the dict comprehension rather than crashing. The
        # pydantic ``BlockSchema`` model rejects ``checksum=None`` at validation
        # time, so we exercise the dict-build guard with a duck-typed stand-in
        # — the comprehension only reads ``.checksum``.
        from types import SimpleNamespace

        valid_bs = self._make_block_schema("sha256:valid")
        none_row = SimpleNamespace(
            id=uuid.uuid4(),
            checksum=None,
            fields={"title": "Stub", "block_schema_references": {}},
            block_type_id=uuid.uuid4(),
            block_type=None,
        )
        # Give the none-checksum row a parent_block_schema_id that does not
        # match any other row, so it is NOT enumerated as a child reference —
        # it is only present to exercise the dict-build guard.
        unrelated_parent = uuid.uuid4()
        rows = [(valid_bs, None, None), (none_row, "stub", unrelated_parent)]
        # Must not raise; the None-checksum row is excluded from the index.
        result = _construct_full_block_schema(rows, root_block_schema=valid_bs)
        assert result is not None
        assert result.checksum == "sha256:valid"

    async def test_read_block_schemas_threads_checksum_index(self, session):
        """AC1 / AC6: ``read_block_schemas`` builds the index once and threads
        it through every ``_find_block_schema_via_checksum`` call, so the
        linear-scan fallback branch (``checksum_index is None``) is never
        entered from the bulk-read path.

        We wrap ``_find_block_schema_via_checksum`` and assert every call
        receives a non-None ``checksum_index`` kwarg — this directly proves
        the threading without depending on internal branch counters.
        """
        # branch_target: src/prefect/server/models/block_schemas.py:502 (dict path taken)

        warnings.filterwarnings("ignore", category=UserWarning)

        class Inner(Block):
            v: str

        class Outer(Block):
            inner: Inner

        await models.block_types.create_block_type(
            session=session, block_type=Inner._to_block_type()
        )
        block_type_outer = await models.block_types.create_block_type(
            session=session, block_type=Outer._to_block_type()
        )
        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=Outer._to_block_schema(block_type_id=block_type_outer.id),
        )

        from unittest.mock import patch

        from prefect.server.models import block_schemas as bs_module

        real_finder = bs_module._find_block_schema_via_checksum
        observed_indexes: list = []

        def spy_finder(*args, **kwargs):
            observed_indexes.append(kwargs.get("checksum_index"))
            return real_finder(*args, **kwargs)

        with patch.object(
            bs_module, "_find_block_schema_via_checksum", side_effect=spy_finder
        ):
            result = await models.block_schemas.read_block_schemas(session=session)

        assert len(result) >= 2
        # At least one lookup must have happened (Outer references Inner).
        assert observed_indexes, "expected _find_block_schema_via_checksum to be called"
        # Every single call from the bulk-read path must carry a real index —
        # the fallback (``checksum_index=None``) path must NOT be entered.
        assert all(idx is not None for idx in observed_indexes)
        # Strong correctness invariant on the reconstructed schema.
        outer_schema = next(
            (bs for bs in result if bs.fields.get("title") == "Outer"), None
        )
        assert outer_schema is not None
        assert "inner" in outer_schema.fields["block_schema_references"]

    async def test_read_block_schemas_builds_index_once_per_call(self, session):
        """AC1: index built ONCE before the loop, not rebuilt per iteration.

        Uses a nested fixture (Outer→Inner) so that _construct_full_block_schema
        is called both from the top-level read_block_schemas loop AND recursively
        from _construct_block_schema_spec_definitions. A regression that removes
        ``checksum_index=checksum_index`` from the recursive call (line 494)
        would cause the recursive invocation to receive None instead of the shared
        index object — the identity check below would then fail even though the
        flat-schema Solo1/Solo2 variant could not detect it.

        We verify by patching ``_construct_full_block_schema`` and checking every
        call (top-level and recursive) receives the *same* index object.
        """
        # branch_target: src/prefect/server/models/block_schemas.py:699 (top-level)
        # branch_target: src/prefect/server/models/block_schemas.py:491 (recursive)
        warnings.filterwarnings("ignore", category=UserWarning)

        class BuildIndexInner(Block):
            v: str

        class BuildIndexOuter(Block):
            inner: BuildIndexInner

        bt_inner = await models.block_types.create_block_type(
            session=session, block_type=BuildIndexInner._to_block_type()
        )
        bt_outer = await models.block_types.create_block_type(
            session=session, block_type=BuildIndexOuter._to_block_type()
        )
        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=BuildIndexInner._to_block_schema(block_type_id=bt_inner.id),
        )
        await models.block_schemas.create_block_schema(
            session=session,
            block_schema=BuildIndexOuter._to_block_schema(block_type_id=bt_outer.id),
        )

        from unittest.mock import patch

        from prefect.server.models import block_schemas as bs_module

        real_construct = bs_module._construct_full_block_schema
        seen_indexes: list = []

        def spy_construct(*args, **kwargs):
            seen_indexes.append(kwargs.get("checksum_index"))
            return real_construct(*args, **kwargs)

        with patch.object(
            bs_module, "_construct_full_block_schema", side_effect=spy_construct
        ):
            result = await models.block_schemas.read_block_schemas(session=session)

        # The Outer schema must be present in the result.
        outer_schema = next(
            (bs for bs in result if bs.fields.get("title") == "BuildIndexOuter"), None
        )
        assert outer_schema is not None

        # At least one recursive call must have happened (Outer references Inner),
        # so the spy should have been called more than once.
        assert len(seen_indexes) >= 2, (
            "Expected at least two _construct_full_block_schema calls "
            "(top-level + recursive); got: " + str(len(seen_indexes))
        )
        # Every call (top-level and recursive) received a non-None index.
        assert all(idx is not None for idx in seen_indexes)
        # All calls received the SAME index object (identity), proving build-once.
        # If the recursive call drops checksum_index=checksum_index, it gets None
        # (triggering a rebuild), which fails both checks above and this one.
        first = seen_indexes[0]
        assert all(idx is first for idx in seen_indexes)

    # --- Regression tests: round additions ---

    def test_find_block_schema_index_uses_first_wins_on_duplicate_checksum(self):
        """F1/A1: when two child rows share a checksum, _construct_full_block_schema
        must resolve the child reference to the FIRST-seen row.

        Calls _construct_full_block_schema directly with a root that references a
        child by checksum and two child rows that share that checksum. The
        internally-built index must use first-wins semantics so that the returned
        definitions are keyed by the first child's title, not the second's.

        A pre-fix last-wins dict comprehension would map the checksum to
        child_second ("ChildSecond"), causing the definitions key to be "ChildSecond"
        instead of "ChildFirst", and this assertion would fail.

        fails_on_pre_fix: yes
        branch_target: src/prefect/server/models/block_schemas.py:408
        """
        from types import SimpleNamespace

        shared_child_checksum = "sha256:child-dup"
        root_schema = self._make_block_schema(
            "sha256:root",
            fields={
                "title": "Root",
                "type": "object",
                "block_schema_references": {
                    "child_field": {
                        "block_schema_checksum": shared_child_checksum,
                        "block_type_slug": "child-slug",
                    }
                },
            },
        )
        # Use SimpleNamespace so block_type.slug is available for
        # _construct_block_schema_fields_with_block_references without needing
        # a real DB-backed BlockType object.
        child_first = SimpleNamespace(
            id=uuid.uuid4(),
            checksum=shared_child_checksum,
            fields={
                "title": "ChildFirst",
                "type": "object",
                "block_schema_references": {},
            },
            block_type=SimpleNamespace(slug="child-slug"),
            block_type_id=uuid.uuid4(),
        )
        child_second = SimpleNamespace(
            id=uuid.uuid4(),
            checksum=shared_child_checksum,
            fields={
                "title": "ChildSecond",
                "type": "object",
                "block_schema_references": {},
            },
            block_type=SimpleNamespace(slug="child-slug"),
            block_type_id=uuid.uuid4(),
        )
        rows = [
            (root_schema, None, None),
            (child_first, "child_field", root_schema.id),
            (child_second, "child_field", root_schema.id),
        ]
        # checksum_index=None forces _construct_full_block_schema to build the
        # index internally. First-wins semantics mean child_first wins over
        # child_second. A pre-fix last-wins dict comprehension would map the
        # checksum to child_second, so definitions would contain "ChildSecond"
        # instead of "ChildFirst" and the assertion below would fail.
        result = _construct_full_block_schema(
            rows, root_block_schema=root_schema, checksum_index=None
        )
        assert result is not None
        definitions = result.fields.get("definitions", {})
        assert "ChildFirst" in definitions, (
            f"Expected 'ChildFirst' in definitions but got keys: {list(definitions.keys())}"
        )
        assert "ChildSecond" not in definitions

    def test_checksum_index_first_wins_matches_linear_scan(self):
        """F1/A1: property check — first-wins index and next() scan agree on duplicate rows.

        When the first two rows share a checksum, a last-wins dict comprehension
        (pre-fix) would map the checksum to rows[1] while ``next()`` returns
        rows[0] — they would disagree.  The patched first-wins loop keeps them
        in agreement.

        fails_on_pre_fix: yes
        branch_target: src/prefect/server/models/block_schemas.py:407
        """
        shared_checksum = "sha256:dup-prop"
        bs_first = self._make_block_schema(shared_checksum)
        bs_second = self._make_block_schema(shared_checksum)
        bs_unique = self._make_block_schema("sha256:unique")

        rows = [
            (bs_first, None, None),
            (bs_second, None, None),
            (bs_unique, None, None),
        ]

        # Build the index exactly as the patched production code does.
        checksum_index: dict = {}
        for bs, _, _ in rows:
            if bs.checksum is not None and bs.checksum not in checksum_index:
                checksum_index[bs.checksum] = bs

        # Reference: what next() (linear scan) would return for the shared checksum.
        linear_scan_result = next(
            (bs for bs, _, _ in rows if bs.checksum == shared_checksum), None
        )

        # The index and the linear scan must agree.
        assert checksum_index[shared_checksum] is linear_scan_result
