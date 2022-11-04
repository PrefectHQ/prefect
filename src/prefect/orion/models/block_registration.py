import json
from pathlib import Path

import sqlalchemy as sa

import prefect
from prefect.logging import get_logger
from prefect.orion import models, schemas

logger = get_logger("orion")

COLLECTIONS_BLOCKS_DATA_PATH = (
    Path(__file__).parent.parent / "collection_blocks_data.json"
)


async def _install_protected_system_blocks(session):
    """Install block types that the system expects to be present"""

    for block in [
        prefect.blocks.system.JSON,
        prefect.blocks.system.DateTime,
        prefect.blocks.system.Secret,
        prefect.filesystems.LocalFileSystem,
        prefect.infrastructure.Process,
    ]:
        async with session.begin():
            block_type = block._to_block_type()
            block_type.is_protected = True

            block_type = await models.block_types.create_block_type(
                session=session, block_type=block_type, override=True
            )
            block_schema = await models.block_schemas.create_block_schema(
                session=session,
                block_schema=block._to_block_schema(block_type_id=block_type.id),
                override=True,
            )


async def register_block_schema(
    session: sa.orm.Session,
    block_schema: schemas.core.BlockSchema,
):
    """
    Stores the provided block schema in the Orion database.

    If a block schema with a matching checksum and version is already saved,
    then the ID of the existing block schema will be returned.

    Args:
        session: A database session.
        block_schema: A block schema object.

    Returns:
        The ID of the registered block schema.
    """

    from prefect.orion.models.block_schemas import (
        create_block_schema,
        read_block_schema_by_checksum,
    )

    existing_block_schema = await read_block_schema_by_checksum(
        session=session, checksum=block_schema.checksum, version=block_schema.version
    )
    if existing_block_schema is None:
        block_schema = await create_block_schema(
            session=session,
            block_schema=block_schema,
        )
        return block_schema.id
    else:
        return existing_block_schema.id


async def register_block_type(
    session: sa.orm.Session,
    block_type: schemas.core.BlockType,
):
    """
    Stores the provided block type in the Orion database.

    If a block type with a matching slug is already saved, then the block type
    will be updated to match the passed in block type.

    Args:
        session: A database session.
        block_type: A block type object.

    Returns:
        The ID of the registered block type.
    """
    from prefect.orion.models.block_types import (
        create_block_type,
        read_block_type_by_slug,
        update_block_type,
    )

    existing_block_type = await read_block_type_by_slug(
        session=session,
        block_type_slug=block_type.slug,
    )
    if existing_block_type is None:
        block_type = await create_block_type(
            session=session,
            block_type=block_type,
        )
        return block_type.id
    else:
        await update_block_type(
            session=session,
            block_type_id=existing_block_type.id,
            block_type=block_type,
        )
        return existing_block_type.id


async def _load_collection_blocks_data():
    """Loads blocks data for whitelisted collections."""
    import anyio

    async with await anyio.open_file(COLLECTIONS_BLOCKS_DATA_PATH, "r") as f:
        return json.loads(await f.read())


async def _register_registry_blocks(session: sa.orm.Session):
    """Registers block from the client block registry."""
    from prefect.blocks.core import Block
    from prefect.utilities.dispatch import get_registry_for_type

    block_registry = get_registry_for_type(Block) or {}

    for block_class in block_registry.values():
        # each block schema gets its own transaction
        async with session.begin():
            block_type_id = await register_block_type(
                session=session,
                block_type=block_class._to_block_type(),
            )
            await register_block_schema(
                session=session,
                block_schema=block_class._to_block_schema(block_type_id=block_type_id),
            )


async def _register_collection_blocks(session: sa.orm.Session):
    """Registers blocks from whitelisted collections."""
    collections_blocks_data = await _load_collection_blocks_data()

    block_types = [
        block_type
        for collection in collections_blocks_data["collections"].values()
        for block_type in collection["block_types"].values()
    ]
    for block_type in block_types:
        # each block schema gets its own transaction
        async with session.begin():
            block_schemas = block_type.pop("block_schemas", [])
            block_type_id = await register_block_type(
                session=session,
                block_type=schemas.core.BlockType.parse_obj(block_type),
            )
            for block_schema in block_schemas:
                await register_block_schema(
                    session=session,
                    block_schema=schemas.core.BlockSchema.parse_obj(
                        {**block_schema, "block_type_id": block_type_id}
                    ),
                )


async def run_block_auto_registration(session: sa.orm.Session):
    """
    Registers all blocks in the client block registry and any blocks from Prefect
    Collections that are configured for auto-registration.

    Args:
        session: A database session.
    """
    await _install_protected_system_blocks(session)
    await _register_registry_blocks(session)
    await _register_collection_blocks(session=session)
