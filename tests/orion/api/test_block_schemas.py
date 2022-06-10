from typing import List
from uuid import uuid4

import pydantic
import pytest

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockSchemaCreate

EMPTY_OBJECT_CHECKSUM = Block._calculate_schema_checksum({})


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


class TestCreateBlockSchema:
    async def test_create_block_schema(self, session, client, block_type_x):
        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(fields={}, block_type_id=block_type_x.id).dict(
                json_compatible=True
            ),
        )
        assert response.status_code == 201
        assert response.json()["checksum"] == EMPTY_OBJECT_CHECKSUM
        block_schema_id = response.json()["id"]

        block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema_id
        )
        assert str(block_schema.id) == block_schema_id

    async def test_create_block_schema_with_existing_checksum_fails(
        self, session, client, block_type_x
    ):
        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(fields={}, block_type_id=block_type_x.id).dict(
                json_compatible=True
            ),
        )
        assert response.status_code == 201

        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(fields={}, block_type_id=block_type_x.id).dict(
                json_compatible=True
            ),
        )
        assert response.status_code == 409
        assert "Identical block schema already exists." in response.json()["detail"]


class TestDeleteBlockSchema:
    async def test_delete_block_schema(self, session, client, block_schemas):
        schema_id = block_schemas[0].id
        response = await client.delete(f"/block_schemas/{schema_id}")
        assert response.status_code == 204

        session.expire_all()

        result = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=schema_id
        )
        assert not result

    async def test_delete_nonexistant_block_schema(self, session, client):
        response = await client.delete(f"/block_schemas/{uuid4()}")
        assert response.status_code == 404


class TestReadBlockSchema:
    async def test_read_all_block_schemas(self, session, client, block_schemas):
        result = await client.post(f"/block_schemas/filter")
        api_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert {s.id for s in api_schemas} == {
            block_schemas[0].id,
            block_schemas[2].id,
            block_schemas[1].id,
        }

    async def test_read_all_block_schemas_filter_block_type_id_x(
        self, session, client, block_schemas, block_type_x
    ):
        result = await client.post(
            f"/block_schemas/filter",
            json=dict(
                block_schema_filter=dict(
                    block_type_id=dict(any_=[str(block_type_x.id)])
                )
            ),
        )
        api_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert [s.id for s in api_schemas] == [block_schemas[i].id for i in (2, 0)]

    async def test_read_all_block_schemas_filter_block_type_id_y(
        self, session, client, block_schemas, block_type_y
    ):
        result = await client.post(
            f"/block_schemas/filter",
            json=dict(
                block_schema_filter=dict(
                    block_type_id=dict(any_=[str(block_type_y.id)])
                )
            ),
        )
        api_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert [s.id for s in api_schemas] == [block_schemas[1].id]

    async def test_read_all_block_schemas_filter_block_type_id_x_and_y(
        self, session, client, block_schemas, block_type_x, block_type_y
    ):
        result = await client.post(
            f"/block_schemas/filter",
            json=dict(
                block_schema_filter=dict(
                    block_type_id=dict(
                        any_=[str(block_type_x.id), str(block_type_y.id)]
                    )
                )
            ),
        )
        api_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert [s.id for s in api_schemas] == [block_schemas[i].id for i in (2, 1, 0)]

    async def test_read_block_schema_by_id(self, session, client, block_schemas):
        schema_id = block_schemas[0].id
        response = await client.get(f"/block_schemas/{schema_id}")
        assert response.status_code == 200

        block_schema_response = pydantic.parse_obj_as(
            schemas.core.BlockSchema, response.json()
        )

        assert block_schema_response.id == schema_id

    async def test_read_block_schema_by_checksum(self, session, client, block_schemas):
        schema_checksum = block_schemas[0].checksum
        response = await client.get(f"/block_schemas/checksum/{schema_checksum}")
        assert response.status_code == 200

        block_schema_response = pydantic.parse_obj_as(
            schemas.core.BlockSchema, response.json()
        )

        assert block_schema_response.id == block_schemas[0].id
        assert block_schema_response.checksum == schema_checksum

    async def test_read_block_schema_with_capability_filter(
        self, client, block_schemas_with_capabilities
    ):
        result = await client.post(
            f"/block_schemas/filter",
            json={"block_capabilities": {"all_": ["fly", "swim"]}},
        )

        assert result.status_code == 200
        block_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert len(block_schemas) == 1
        assert block_schemas[0].id == block_schemas_with_capabilities[0].id

        result = await client.post(
            f"/block_schemas/filter", json={"block_capabilities": {"all_": ["fly"]}}
        )

        assert result.status_code == 200
        block_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert len(block_schemas) == 2
        assert [block_schema.id for block_schema in block_schemas] == [
            block_schemas_with_capabilities[0].id,
            block_schemas_with_capabilities[1].id,
        ]

        result = await client.post(
            f"/block_schemas/filter",
            json={"block_capabilities": {"all_": ["swim"]}},
        )

        assert result.status_code == 200
        block_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert len(block_schemas) == 1
        assert block_schemas[0].id == block_schemas_with_capabilities[0].id
