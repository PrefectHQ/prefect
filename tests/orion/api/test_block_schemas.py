from typing import List
from uuid import uuid4

import pydantic
import pytest
from fastapi import status

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockSchemaCreate
from prefect.orion.schemas.core import DEFAULT_BLOCK_SCHEMA_VERSION

EMPTY_OBJECT_CHECKSUM = Block._calculate_schema_checksum({})


@pytest.fixture
async def system_block_type(session):
    block_type = await models.block_types.create_block_type(
        session=session,
        block_type=schemas.core.BlockType(
            name="System Block", slug="system-block", is_protected=True
        ),
    )
    await session.commit()
    return block_type


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
        assert response.json()["version"] == DEFAULT_BLOCK_SCHEMA_VERSION
        block_schema_id = response.json()["id"]

        block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema_id
        )
        assert str(block_schema.id) == block_schema_id

    async def test_create_block_schema_is_idempotent(self, client, block_type_x):
        response_1 = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(fields={}, block_type_id=block_type_x.id).dict(
                json_compatible=True
            ),
        )
        assert response_1.status_code == status.HTTP_201_CREATED

        response_2 = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(fields={}, block_type_id=block_type_x.id).dict(
                json_compatible=True
            ),
        )
        assert response_2.status_code == status.HTTP_200_OK
        assert response_1.json() == response_2.json()

    async def test_create_block_schema_for_system_block_type_succeeds(
        self, system_block_type, client
    ):
        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(fields={}, block_type_id=system_block_type.id).dict(
                json_compatible=True
            ),
        )
        assert response.status_code == status.HTTP_201_CREATED

    async def test_create_block_schema_with_version(
        self, session, client, block_type_x
    ):
        response = await client.post(
            "/block_schemas/",
            json=BlockSchemaCreate(
                fields={}, block_type_id=block_type_x.id, version="1.0.0"
            ).dict(json_compatible=True),
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["checksum"] == EMPTY_OBJECT_CHECKSUM
        assert response.json()["version"] == "1.0.0"
        block_schema_id = response.json()["id"]

        block_schema = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=block_schema_id
        )
        assert str(block_schema.id) == block_schema_id
        assert block_schema.version == "1.0.0"


class TestDeleteBlockSchema:
    async def test_delete_block_schema(self, session, client, block_schemas):
        schema_id = block_schemas[0].id
        response = await client.delete(f"/block_schemas/{schema_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        session.expire_all()

        result = await models.block_schemas.read_block_schema(
            session=session, block_schema_id=schema_id
        )
        assert not result

    async def test_delete_nonexistant_block_schema(self, session, client):
        response = await client.delete(f"/block_schemas/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_delete_block_schema_for_system_block_type_fails(
        self, session, system_block_type, client
    ):
        block_schema = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={}, block_type_id=system_block_type.id
            ),
        )
        await session.commit()

        response = await client.delete(f"/block_schemas/{block_schema.id}")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert (
            response.json()["detail"]
            == "Block schemas for protected block types cannot be deleted."
        )


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
                block_schemas=dict(block_type_id=dict(any_=[str(block_type_x.id)]))
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
                block_schemas=dict(block_type_id=dict(any_=[str(block_type_y.id)]))
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
                block_schemas=dict(
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
        assert response.status_code == status.HTTP_200_OK

        block_schema_response = pydantic.parse_obj_as(
            schemas.core.BlockSchema, response.json()
        )

        assert block_schema_response.id == schema_id

    async def test_read_block_schema_by_checksum(self, session, client, block_schemas):
        schema_checksum = block_schemas[0].checksum
        response = await client.get(f"/block_schemas/checksum/{schema_checksum}")
        assert response.status_code == status.HTTP_200_OK

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
            json=dict(
                block_schemas=dict(block_capabilities=dict(all_=["fly", "swim"]))
            ),
        )

        assert result.status_code == status.HTTP_200_OK
        block_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert len(block_schemas) == 1
        assert block_schemas[0].id == block_schemas_with_capabilities[0].id

        result = await client.post(
            f"/block_schemas/filter",
            json=dict(block_schemas=dict(block_capabilities=dict(all_=["fly"]))),
        )

        assert result.status_code == status.HTTP_200_OK
        block_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert len(block_schemas) == 2
        assert [block_schema.id for block_schema in block_schemas] == [
            block_schemas_with_capabilities[1].id,
            block_schemas_with_capabilities[0].id,
        ]

        result = await client.post(
            f"/block_schemas/filter",
            json=dict(block_schemas=dict(block_capabilities=dict(all_=["swim"]))),
        )

        assert result.status_code == status.HTTP_200_OK
        block_schemas = pydantic.parse_obj_as(
            List[schemas.core.BlockSchema], result.json()
        )
        assert len(block_schemas) == 1
        assert block_schemas[0].id == block_schemas_with_capabilities[0].id

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
        await session.commit()
        block_schema_1 = await models.block_schemas.create_block_schema(
            session=session,
            block_schema=schemas.actions.BlockSchemaCreate(
                fields={}, block_type_id=block_type_x.id, version="1.1.0"
            ),
        )
        await session.commit()

        assert block_schema_0.checksum == block_schema_1.checksum
        assert block_schema_0.id != block_schema_1.id

        # Read first version with version query parameter
        response_1 = await client.get(
            f"/block_schemas/checksum/{block_schema_0.checksum}?version=1.0.1"
        )
        assert response_1.status_code == status.HTTP_200_OK

        block_schema_response_1 = pydantic.parse_obj_as(
            schemas.core.BlockSchema, response_1.json()
        )

        assert block_schema_response_1.id == block_schema_0.id

        # Read second version with version query parameter
        response_2 = await client.get(
            f"/block_schemas/checksum/{block_schema_1.checksum}?version=1.1.0"
        )
        assert response_2.status_code == status.HTTP_200_OK

        block_schema_response_2 = pydantic.parse_obj_as(
            schemas.core.BlockSchema, response_2.json()
        )

        assert block_schema_response_2.id == block_schema_1.id

        # Read without version. Should return most recently created block schema.
        response_3 = await client.get(
            f"/block_schemas/checksum/{block_schema_0.checksum}"
        )
        assert response_3.status_code == status.HTTP_200_OK

        block_schema_response_3 = pydantic.parse_obj_as(
            schemas.core.BlockSchema, response_3.json()
        )

        assert block_schema_response_3.id == block_schema_1.id
