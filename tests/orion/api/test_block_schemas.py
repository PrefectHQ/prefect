from typing import List
from uuid import uuid4

import pydantic
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockSchemaCreate


@pytest.fixture
async def block_schemas(session):
    block_schema_0 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.core.BlockSchema(
            name="x",
            version="1.0",
            type="abc",
        ),
    )
    await session.commit()

    block_schema_1 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.core.BlockSchema(
            name="y",
            version="1.0",
            type="abc",
        ),
    )
    await session.commit()

    block_schema_2 = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.core.BlockSchema(
            name="x",
            version="2.0",
            type=None,
        ),
    )
    await session.commit()

    return block_schema_0, block_schema_1, block_schema_2


class TestCreateBlockSchema:
    async def test_create_block_schema(self, session, client):
        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(
                name="x", version="1.0", type=None, fields={}
            ).dict(),
        )
        assert response.status_code == 201
        assert response.json()["name"] == "x"
        block_schema_id = response.json()["id"]

        block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema_id
        )
        assert str(block_schema.id) == block_schema_id

    async def test_create_block_schema_with_existing_name_and_version_fails(
        self, session, client
    ):
        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(
                name="x", version="1.0", type=None, fields={}
            ).dict(),
        )
        assert response.status_code == 201

        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(
                name="x", version="1.0", type="abc", fields={}
            ).dict(),
        )
        assert response.status_code == 409
        assert 'Block schema "x/1.0" already exists.' in response.json()["detail"]

    @pytest.mark.parametrize(
        "name",
        [
            "my block schema",
            "my:block schema",
            r"my\block schema",
            "my👍block_schema",
            "my|block schema",
        ],
    )
    async def test_create_block_schema_with_nonstandard_characters(self, client, name):
        response = await client.post(
            "/block_schemas/", json=dict(name=name, version="1.0")
        )
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "name",
        [
            "my%block_schema",
            "my/block schema",
        ],
    )
    async def test_create_block_schema_with_invalid_characters(self, client, name):
        response = await client.post(
            "/block_schemas/", json=dict(name=name, version="1.0")
        )
        assert response.status_code == 422


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
        assert [s.id for s in api_schemas] == [
            block_schemas[0].id,
            block_schemas[2].id,
            block_schemas[1].id,
        ]

    async def test_read_block_schemas_by_type(self, session, client, block_schemas):
        result = await client.post(f"/block_schemas/filter", json=dict(type="abc"))
        api_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert [s.id for s in api_schemas] == [block_schemas[0].id, block_schemas[1].id]

    async def test_read_block_schemas_by_name(self, session, client, block_schemas):
        result = await client.get(f"/block_schemas/x/versions")
        api_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert [s.id for s in api_schemas] == [block_schemas[0].id, block_schemas[2].id]

    async def test_read_block_schemas_by_name_and_version(
        self, session, client, block_schemas
    ):
        result = await client.get(f"/block_schemas/x/versions/1.0")
        api_schema = schemas.core.BlockSchema.parse_obj(result.json())
        assert api_schema.id == block_schemas[0].id

    async def test_read_block_schemas_by_name_and_version_2(
        self, session, client, block_schemas
    ):
        result = await client.get(f"/block_schemas/x/versions/2.0")
        api_schema = schemas.core.BlockSchema.parse_obj(result.json())
        assert api_schema.id == block_schemas[2].id

    async def test_read_missing_block_schema_by_name_and_version(self, session, client):
        result = await client.get(f"/block_schemas/x/versions/5.0")
        assert result.status_code == 404

        result = await client.get(f"/block_schemas/xyzabc/versions/1.0")
        assert result.status_code == 404

    @pytest.mark.parametrize(
        "name",
        [
            "my block schema",
            "my:block schema",
            r"my\block schema",
            "my👍block_schema",
            "my|block schema",
        ],
    )
    async def test_read_block_schema_by_name_with_nonstandard_characters(
        self, client, name
    ):
        response = await client.post(
            "/block_schemas/", json=dict(name=name, version="1.0")
        )
        block_schema_id = response.json()["id"]

        response = await client.get(f"/block_schemas/{name}/versions")
        assert response.status_code == 200
        assert response.json()[0]["id"] == block_schema_id

    @pytest.mark.parametrize(
        "version",
        [
            "my block schema",
            "my:block schema",
            r"my\block schema",
            "my👍block_schema",
            "my|block schema",
        ],
    )
    async def test_read_block_schema_by_name_with_nonstandard_characters_version(
        self, client, version
    ):
        response = await client.post(
            "/block_schemas/", json=dict(name="block schema", version=version)
        )
        block_schema_id = response.json()["id"]

        response = await client.get(f"/block_schemas/block schema/versions/{version}")
        assert response.status_code == 200
        assert response.json()["id"] == block_schema_id
