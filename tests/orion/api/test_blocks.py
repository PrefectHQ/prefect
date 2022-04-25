from typing import List
from uuid import uuid4

import pydantic
import pytest

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockCreate, BlockUpdate
from prefect.orion.schemas.core import Block


@pytest.fixture
async def block_specs(session):
    block_spec_0 = await models.block_specs.create_block_spec(
        session=session,
        block_spec=schemas.core.BlockSpec(
            name="x",
            version="1.0",
            type="abc",
        ),
    )
    await session.commit()

    block_spec_1 = await models.block_specs.create_block_spec(
        session=session,
        block_spec=schemas.core.BlockSpec(
            name="y",
            version="1.0",
            type="abc",
        ),
    )
    await session.commit()

    block_spec_2 = await models.block_specs.create_block_spec(
        session=session,
        block_spec=schemas.core.BlockSpec(
            name="x",
            version="2.0",
            type=None,
        ),
    )
    await session.commit()

    return block_spec_0, block_spec_1, block_spec_2


class TestCreateBlock:
    async def test_create_block(self, session, client, block_specs):
        response = await client.post(
            "/blocks/",
            json=BlockCreate(
                name="x", data=dict(y=1), block_spec_id=block_specs[0].id
            ).dict(json_compatible=True),
        )
        assert response.status_code == 201
        result = Block.parse_obj(response.json())

        assert result.name == "x"
        assert result.data == dict(y=1)
        assert result.block_spec_id == block_specs[0].id
        assert result.block_spec.name == block_specs[0].name

        response = await client.get(f"/blocks/{result.id}")
        api_block = Block.parse_obj(response.json())
        assert api_block.name == "x"
        assert api_block.data == dict(y=1)
        assert result.block_spec_id == block_specs[0].id
        assert result.block_spec.name == block_specs[0].name

    async def test_create_block_already_exists(self, session, client, block_specs):
        response = await client.post(
            "/blocks/",
            json=BlockCreate(
                name="x", data=dict(y=1), block_spec_id=block_specs[0].id
            ).dict(json_compatible=True),
        )
        assert response.status_code == 201

        response = await client.post(
            "/blocks/",
            json=BlockCreate(
                name="x", data=dict(y=1), block_spec_id=block_specs[0].id
            ).dict(json_compatible=True),
        )
        assert response.status_code == 409

    async def test_create_block_with_same_name_but_different_block_spec(
        self, session, client, block_specs
    ):
        response = await client.post(
            "/blocks/",
            json=BlockCreate(
                name="x", data=dict(y=1), block_spec_id=block_specs[0].id
            ).dict(json_compatible=True),
        )
        assert response.status_code == 201

        response = await client.post(
            "/blocks/",
            json=BlockCreate(
                name="x", data=dict(y=1), block_spec_id=block_specs[1].id
            ).dict(json_compatible=True),
        )
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "name",
        [
            "my block",
            "my:block",
            r"my\block",
            "my👍block",
            "my|block",
        ],
    )
    async def test_create_block_with_nonstandard_characters(
        self, client, name, block_specs
    ):
        response = await client.post(
            "/blocks/",
            json=dict(name=name, data=dict(), block_spec_id=str(block_specs[0].id)),
        )
        assert response.status_code == 201

    @pytest.mark.parametrize(
        "name",
        [
            "my%block",
            "my/block",
        ],
    )
    async def test_create_block_with_invalid_characters(
        self, client, name, block_specs
    ):
        response = await client.post(
            "/blocks/",
            json=dict(name=name, data=dict(), block_spec_id=str(block_specs[0].id)),
        )
        assert response.status_code == 422


class TestReadBlock:
    async def test_read_missing_block(self, client):
        response = await client.get(f"/blocks/{uuid4()}")
        assert response.status_code == 404


class TestReadBlocks:
    @pytest.fixture(autouse=True)
    async def blocks(self, session, block_specs):

        blocks = []
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[0].id, name="Block 1"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[1].id, name="Block 2"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[2].id, name="Block 3"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[1].id, name="Block 4"
                ),
            )
        )
        blocks.append(
            await models.blocks.create_block(
                session=session,
                block=schemas.core.Block(
                    block_spec_id=block_specs[2].id, name="Block 5"
                ),
            )
        )

        session.add_all(blocks)
        await session.commit()
        return blocks

    async def test_read_blocks(self, client, blocks):
        response = await client.post("/blocks/filter")
        assert response.status_code == 200
        read_blocks = pydantic.parse_obj_as(List[schemas.core.Block], response.json())
        assert {b.id for b in read_blocks} == {b.id for b in blocks}
        # sorted by block spec name, block spec version (desc), block name
        assert [b.id for b in read_blocks] == [
            blocks[2].id,
            blocks[4].id,
            blocks[0].id,
            blocks[1].id,
            blocks[3].id,
        ]

    async def test_read_blocks_limit_offset(self, client, blocks):
        # sorted by block spec name, block spec version (desc), block name
        response = await client.post("/blocks/filter", json=dict(limit=2))
        read_blocks = pydantic.parse_obj_as(List[schemas.core.Block], response.json())
        assert [b.id for b in read_blocks] == [blocks[2].id, blocks[4].id]

        response = await client.post("/blocks/filter", json=dict(limit=2, offset=2))
        read_blocks = pydantic.parse_obj_as(List[schemas.core.Block], response.json())
        assert [b.id for b in read_blocks] == [blocks[0].id, blocks[1].id]

    async def test_read_blocks_type(self, client, blocks):
        response = await client.post("/blocks/filter", json=dict(block_spec_type="abc"))
        read_blocks = pydantic.parse_obj_as(List[schemas.core.Block], response.json())
        assert [b.id for b in read_blocks] == [blocks[0].id, blocks[1].id, blocks[3].id]


class TestDeleteBlock:
    async def test_delete_block(self, session, client, block_specs):
        response = await client.post(
            "/blocks/",
            json=BlockCreate(
                name="x", data=dict(y=1), block_spec_id=block_specs[0].id
            ).dict(json_compatible=True),
        )
        result = Block.parse_obj(response.json())

        response = await client.get(f"/blocks/{result.id}")
        assert response.status_code == 200

        response = await client.delete(f"/blocks/{result.id}")
        assert response.status_code == 204

        response = await client.get(f"/blocks/{result.id}")
        assert response.status_code == 404

    async def test_delete_missing_block(self, session, client, block_specs):
        response = await client.delete(f"/blocks/{uuid4()}")
        assert response.status_code == 404


class TestDefaultStorageBlock:
    @pytest.fixture
    async def storage_block_spec(self, session):
        storage_block_spec = await models.block_specs.create_block_spec(
            session=session,
            block_spec=schemas.core.BlockSpec(
                name="storage-type",
                version="1.0",
                type="STORAGE",
            ),
        )
        await session.commit()
        return storage_block_spec

    @pytest.fixture
    async def storage_block(self, session, storage_block_spec):
        block = await models.blocks.create_block(
            session=session,
            block=Block(
                name="storage", data=dict(), block_spec_id=storage_block_spec.id
            ),
        )
        await session.commit()
        return block

    async def test_set_default_storage_block(self, client, storage_block):

        response = await client.post(f"/blocks/get_default_storage_block")
        assert response.status_code == 204
        assert not response.content

        await client.post(f"/blocks/{storage_block.id}/set_default_storage_block")

        response = await client.post(f"/blocks/get_default_storage_block")
        assert response.status_code == 200
        assert response.json()["id"] == str(storage_block.id)

    async def test_set_default_fails_if_not_storage_block(
        self, session, client, block_specs
    ):
        non_storage_block = await models.blocks.create_block(
            session=session,
            block=Block(
                name="non-storage", data=dict(), block_spec_id=block_specs[0].id
            ),
        )
        await session.commit()

        response = await client.post(
            f"/blocks/{non_storage_block.id}/set_default_storage_block"
        )
        assert response.status_code == 422

        response = await client.post(f"/blocks/get_default_storage_block")
        assert not response.content

    async def test_get_default_storage_block(self, client, storage_block):
        await client.post(f"/blocks/{storage_block.id}/set_default_storage_block")

        response = await client.post(f"/blocks/get_default_storage_block")
        result = schemas.core.Block.parse_obj(response.json())
        assert result.id == storage_block.id

    async def test_clear_default_storage_block(self, client, storage_block):
        await client.post(f"/blocks/{storage_block.id}/set_default_storage_block")

        response = await client.post(f"/blocks/get_default_storage_block")
        assert response.json()["id"] == str(storage_block.id)

        await client.post(f"/blocks/clear_default_storage_block")

        response = await client.post(f"/blocks/get_default_storage_block")
        assert not response.content
