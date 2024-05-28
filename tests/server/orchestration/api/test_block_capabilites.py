import pytest
from starlette import status

from prefect.blocks.core import Block
from prefect.server import models


@pytest.fixture
async def block_schemas(session):
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


class TestListAvailableBlockCapabilities:
    async def test_list_available_block_capabilities(self, client, block_schemas):
        response = await client.get("/block_capabilities/")

        assert response.status_code == status.HTTP_200_OK
        assert sorted(response.json()) == sorted(["run", "fly", "swim"])

    async def test_list_available_block_capabilities_no_block_schemas(self, client):
        response = await client.get("/block_capabilities/")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
