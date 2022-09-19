import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

import prefect.orion.schemas as schemas

COLLECTIONS_BLOCKS_DATA_PATH = Path(__file__).parent / "collection_blocks_data.json"


async def register_block_type(
    session: AsyncSession,
    block_type: schemas.core.BlockType,
    should_override: bool = False,
):
    from prefect.orion.models.block_types import (
        create_block_type,
        read_block_type_by_slug,
        update_block_type,
    )

    existing_block_type = await read_block_type_by_slug(
        session=session,
        block_type_slug=block_type.slug,
    )
    if existing_block_type is None or should_override:
        block_type = await create_block_type(
            session=session,
            block_type=block_type,
            override=should_override,
        )
        return block_type.id
    else:
        await update_block_type(
            session=session,
            block_type_id=existing_block_type.id,
            block_type=block_type,
        )
        return existing_block_type.id


async def register_block_schema(
    session: AsyncSession,
    block_schema: schemas.core.BlockSchema,
    should_override: bool = False,
):
    from prefect.orion.models.block_schemas import (
        create_block_schema,
        read_block_schema_by_checksum,
    )

    existing_block_schema = await read_block_schema_by_checksum(
        session=session, checksum=block_schema.checksum, version=block_schema.version
    )
    if existing_block_schema is None or should_override:
        block_schema = await create_block_schema(
            session=session,
            block_schema=block_schema,
            override=should_override,
        )
        return block_schema.id
    else:
        return existing_block_schema.id


async def _load_collection_blocks_data():
    import aiofiles

    async with aiofiles.open(COLLECTIONS_BLOCKS_DATA_PATH, "r") as f:
        return json.loads(await f.read())


async def _register_blocks_in_registry(
    session: AsyncSession, should_override: bool = False
):
    from prefect.blocks.core import Block
    from prefect.utilities.dispatch import get_registry_for_type

    block_registry = get_registry_for_type(Block)

    if block_registry is None:
        return

    for block_class in block_registry.values():
        # each block schema gets its own transaction
        async with session.begin():
            block_type_id = await register_block_type(
                session=session,
                block_type=block_class._to_block_type(),
                should_override=should_override,
            )
            await register_block_schema(
                session=session,
                block_schema=block_class._to_block_schema(block_type_id=block_type_id),
                should_override=should_override,
            )


async def _register_collection_blocks(
    session: AsyncSession, should_override: bool = False
):
    collections_blocks_data = await _load_collection_blocks_data()

    block_types = [
        block_type
        for collection in collections_blocks_data["collections"].values()
        for block_type in collection["block_types"].values()
    ]
    for block_type in block_types:
        async with session.begin():
            block_type_id = await register_block_type(
                session=session,
                block_type=schemas.core.BlockType.parse_obj(block_type),
                should_override=should_override,
            )
            for block_schema in block_type["block_schemas"]:
                print({**block_schema, "block_type_id": block_type_id})
                await register_block_schema(
                    session=session,
                    block_schema=schemas.core.BlockSchema.parse_obj(
                        {**block_schema, "block_type_id": block_type_id}
                    ),
                    should_override=should_override,
                )


async def run_block_auto_registration(
    session: AsyncSession, should_override: bool = False
):
    async with session:
        await _register_blocks_in_registry(session, should_override=should_override)
        await _register_collection_blocks(
            session=session, should_override=should_override
        )
