import pytest

from prefect.blocks.core import Block
from prefect.blocks.system import Secret
from prefect.orion.models.block_registration import (
    _load_collection_blocks_data,
    register_block_schema,
    register_block_type,
    run_block_auto_registration,
)
from prefect.orion.models.block_schemas import read_block_schema_by_checksum
from prefect.orion.models.block_types import read_block_type_by_slug, read_block_types
from prefect.settings import PREFECT_ORION_BLOCKS_REGISTER_ON_START, temporary_settings
from prefect.utilities.dispatch import get_registry_for_type


@pytest.fixture(scope="module")
async def expected_number_of_registered_block_types():
    collections_blocks_data = await _load_collection_blocks_data()

    block_types_from_collections = [
        block_type
        for collection in collections_blocks_data["collections"].values()
        for block_type in collection["block_types"].values()
    ]
    block_registry = get_registry_for_type(Block) or {}
    return len(block_types_from_collections) + len(block_registry.values())


class TestRunAutoRegistration:
    async def test_full_registration_with_empty_database(
        self, session, expected_number_of_registered_block_types
    ):
        starting_block_types = await read_block_types(session)
        assert len(starting_block_types) == 0
        await session.commit()

        await run_block_auto_registration(session=session)
        await session.commit()

        registered_blocks = await read_block_types(session)
        assert len(registered_blocks) == expected_number_of_registered_block_types

    async def test_registration_works_with_populated_database(
        self, session, expected_number_of_registered_block_types
    ):
        with temporary_settings({PREFECT_ORION_BLOCKS_REGISTER_ON_START: True}):
            await run_block_auto_registration(session=session)
            await session.commit()

            registered_blocks = await read_block_types(session)
            assert len(registered_blocks) == expected_number_of_registered_block_types


class TestRegisterBlockType:
    async def test_register_new_block_type(self, session):
        read_block_type = await read_block_type_by_slug(
            session, block_type_slug="secret"
        )
        assert read_block_type is None

        registered_block_type_id = await register_block_type(
            session=session, block_type=Secret._to_block_type()
        )

        read_block_type = await read_block_type_by_slug(
            session, block_type_slug="secret"
        )

        assert registered_block_type_id == read_block_type.id

    async def test_register_existing_block_type(self, session):
        first_block_type_id = await register_block_type(
            session=session, block_type=Secret._to_block_type()
        )

        Secret._description = "I have overwritten this description"

        second_block_type_id = await register_block_type(
            session=session, block_type=Secret._to_block_type()
        )

        assert first_block_type_id == second_block_type_id

        read_block_type = await read_block_type_by_slug(
            session, block_type_slug="secret"
        )
        assert read_block_type.description == Secret._description


class TestRegisterBlockSchema:
    async def test_register_new_block_schema(self, session):
        block_type_id = await register_block_type(
            session=session, block_type=Secret._to_block_type()
        )

        registered_block_schema_id = await register_block_schema(
            session, block_schema=Secret._to_block_schema(block_type_id=block_type_id)
        )

        read_block_schema = await read_block_schema_by_checksum(
            session,
            checksum=Secret._calculate_schema_checksum(),
            version=Secret.get_block_schema_version(),
        )

        assert registered_block_schema_id == read_block_schema.id

    async def test_register_existing_block_schema(self, session):
        block_type_id = await register_block_type(
            session=session, block_type=Secret._to_block_type()
        )

        first_registered_block_schema_id = await register_block_schema(
            session, block_schema=Secret._to_block_schema(block_type_id=block_type_id)
        )

        second_registered_block_schema_id = await register_block_schema(
            session, block_schema=Secret._to_block_schema(block_type_id=block_type_id)
        )

        assert first_registered_block_schema_id == second_registered_block_schema_id
