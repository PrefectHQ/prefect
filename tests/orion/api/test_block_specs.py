from typing import List
from uuid import uuid4

import pydantic
import pytest
from fastapi import status

from prefect.orion import models, schemas
from prefect.orion.schemas.actions import BlockSpecCreate


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


class TestCreateBlockSpec:
    async def test_create_block_spec(self, session, client):
        response = await client.post(
            "/block_specs/",
            json=BlockSpecCreate(name="x", version="1.0", type=None, fields={}).dict(),
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["name"] == "x"
        block_spec_id = response.json()["id"]

        block_spec = await models.block_specs.read_block_spec(
            session=session, block_spec_id=block_spec_id
        )
        assert str(block_spec.id) == block_spec_id

    async def test_create_block_spec_with_existing_name_and_version_fails(
        self, session, client
    ):
        response = await client.post(
            "/block_specs/",
            json=BlockSpecCreate(name="x", version="1.0", type=None, fields={}).dict(),
        )
        assert response.status_code == status.HTTP_201_CREATED

        response = await client.post(
            "/block_specs/",
            json=BlockSpecCreate(name="x", version="1.0", type="abc", fields={}).dict(),
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert 'Block spec "x/1.0" already exists.' in response.json()["detail"]

    @pytest.mark.parametrize(
        "name",
        [
            "my block spec",
            "my:block spec",
            r"my\block spec",
            "my👍block_spec",
            "my|block spec",
        ],
    )
    async def test_create_block_spec_with_nonstandard_characters(self, client, name):
        response = await client.post(
            "/block_specs/", json=dict(name=name, version="1.0")
        )
        assert response.status_code == status.HTTP_201_CREATED

    @pytest.mark.parametrize(
        "name",
        [
            "my%block_spec",
            "my/block spec",
        ],
    )
    async def test_create_block_spec_with_invalid_characters(self, client, name):
        response = await client.post(
            "/block_specs/", json=dict(name=name, version="1.0")
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestDeleteBlockSpec:
    async def test_delete_block_spec(self, session, client, block_specs):
        spec_id = block_specs[0].id
        response = await client.delete(f"/block_specs/{spec_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        session.expire_all()

        result = await models.block_specs.read_block_spec(
            session=session, block_spec_id=spec_id
        )
        assert not result

    async def test_delete_nonexistant_block_spec(self, session, client):
        response = await client.delete(f"/block_specs/{uuid4()}")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadBlockSpec:
    async def test_read_all_block_specs(self, session, client, block_specs):
        result = await client.post(f"/block_specs/filter")
        api_specs = pydantic.parse_obj_as(List[schemas.core.BlockSpec], result.json())
        assert [s.id for s in api_specs] == [
            block_specs[0].id,
            block_specs[2].id,
            block_specs[1].id,
        ]

    async def test_read_block_specs_by_type(self, session, client, block_specs):
        result = await client.post(f"/block_specs/filter", json=dict(type="abc"))
        api_specs = pydantic.parse_obj_as(List[schemas.core.BlockSpec], result.json())
        assert [s.id for s in api_specs] == [block_specs[0].id, block_specs[1].id]

    async def test_read_block_specs_by_name(self, session, client, block_specs):
        result = await client.get(f"/block_specs/x/versions")
        api_specs = pydantic.parse_obj_as(List[schemas.core.BlockSpec], result.json())
        assert [s.id for s in api_specs] == [block_specs[0].id, block_specs[2].id]

    async def test_read_block_specs_by_name_and_version(
        self, session, client, block_specs
    ):
        result = await client.get(f"/block_specs/x/versions/1.0")
        api_spec = schemas.core.BlockSpec.parse_obj(result.json())
        assert api_spec.id == block_specs[0].id

    async def test_read_block_specs_by_name_and_version_2(
        self, session, client, block_specs
    ):
        result = await client.get(f"/block_specs/x/versions/2.0")
        api_spec = schemas.core.BlockSpec.parse_obj(result.json())
        assert api_spec.id == block_specs[2].id

    async def test_read_missing_block_spec_by_name_and_version(self, session, client):
        result = await client.get(f"/block_specs/x/versions/5.0")
        assert result.status_code == status.HTTP_404_NOT_FOUND

        result = await client.get(f"/block_specs/xyzabc/versions/1.0")
        assert result.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        "name",
        [
            "my block spec",
            "my:block spec",
            r"my\block spec",
            "my👍block_spec",
            "my|block spec",
        ],
    )
    async def test_read_block_spec_by_name_with_nonstandard_characters(
        self, client, name
    ):
        response = await client.post(
            "/block_specs/", json=dict(name=name, version="1.0")
        )
        block_spec_id = response.json()["id"]

        response = await client.get(f"/block_specs/{name}/versions")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()[0]["id"] == block_spec_id

    @pytest.mark.parametrize(
        "version",
        [
            "my block spec",
            "my:block spec",
            r"my\block spec",
            "my👍block_spec",
            "my|block spec",
        ],
    )
    async def test_read_block_spec_by_name_with_nonstandard_characters_version(
        self, client, version
    ):
        response = await client.post(
            "/block_specs/", json=dict(name="block spec", version=version)
        )
        block_spec_id = response.json()["id"]

        response = await client.get(f"/block_specs/block spec/versions/{version}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == block_spec_id
