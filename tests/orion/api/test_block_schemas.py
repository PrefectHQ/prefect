import hashlib
import json
from typing import List
from uuid import uuid4

import pydantic
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockSchemaCreate
from prefect.utilities.hashing import hash_objects

EMPTY_OBJECT_CHECKSUM = f"sha256:{hash_objects({}, hash_algo=hashlib.sha256)}"


@pytest.fixture
async def block_schemas(session, block_type_x, block_type_y):
    block_schema_0 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={}, type="abc", block_type_id=block_type_x.id
        ),
    )
    await session.commit()

    block_schema_1 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={"x": {"type": "int"}}, type="abc", block_type_id=block_type_y.id
        ),
    )
    await session.commit()

    block_schema_2 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={"y": {"type": "int"}}, type=None, block_type_id=block_type_x.id
        ),
    )
    await session.commit()

    return block_schema_0, block_schema_1, block_schema_2


class TestCreateBlockSchema:
    async def test_create_block_schema(self, session, client, block_type_x):
        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(
                type=None, fields={}, block_type_id=block_type_x.id
            ).dict(json_compatible=True),
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
            json=BlockSchemaCreate(
                type=None, fields={}, block_type_id=block_type_x.id
            ).dict(json_compatible=True),
        )
        assert response.status_code == 201

        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(
                type=None, fields={}, block_type_id=block_type_x.id
            ).dict(json_compatible=True),
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

    async def test_read_block_schemas_by_type(self, session, client, block_schemas):
        result = await client.post(f"/block_schemas/filter", json=dict(type="abc"))
        api_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert {s.id for s in api_schemas} == {block_schemas[0].id, block_schemas[1].id}

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
