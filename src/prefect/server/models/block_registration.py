import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Union, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from prefect.blocks.core import Block
from prefect.blocks.system import JSON, DateTime, Secret
from prefect.blocks.webhook import Webhook
from prefect.filesystems import LocalFileSystem
from prefect.logging import get_logger
from prefect.server import models, schemas

if TYPE_CHECKING:
    import logging

    from prefect.client.schemas import BlockSchema as ClientBlockSchema
    from prefect.client.schemas import BlockType as ClientBlockType

logger: "logging.Logger" = get_logger("server")

COLLECTIONS_BLOCKS_DATA_PATH = (
    Path(__file__).parent.parent / "collection_blocks_data.json"
)


async def _install_protected_system_blocks(session: AsyncSession) -> None:
    """Install block types that the system expects to be present"""
    protected_system_blocks = cast(
        List[Block], [Webhook, JSON, DateTime, Secret, LocalFileSystem]
    )

    for block in protected_system_blocks:
        async with session.begin():
            block_type = block._to_block_type()

            server_block_type = schemas.core.BlockType.model_validate(
                block_type.model_dump()
            )
            block_type.is_protected = True
            server_block_type.is_protected = True

            orm_block_type = await models.block_types.create_block_type(
                session=session, block_type=server_block_type, override=True
            )
            assert orm_block_type is not None, (
                f"Failed to create block type {block_type}"
            )

            await models.block_schemas.create_block_schema(
                session=session,
                block_schema=block._to_block_schema(block_type_id=orm_block_type.id),
                override=True,
            )


async def register_block_schema(
    session: AsyncSession,
    block_schema: Union[schemas.core.BlockSchema, "ClientBlockSchema"],
) -> UUID:
    """
    Stores the provided block schema in the Prefect REST API database.

    If a block schema with a matching checksum and version is already saved,
    then the ID of the existing block schema will be returned.

    Args:
        session: A database session.
        block_schema: A block schema object.

    Returns:
        The ID of the registered block schema.
    """

    from prefect.server.models.block_schemas import (
        create_block_schema,
        read_block_schema_by_checksum,
    )

    existing_block_schema = await read_block_schema_by_checksum(
        session=session, checksum=block_schema.checksum, version=block_schema.version
    )
    if existing_block_schema is None:
        new_block_schema = await create_block_schema(
            session=session,
            block_schema=block_schema,
        )
        return new_block_schema.id
    else:
        return existing_block_schema.id


async def register_block_type(
    session: AsyncSession,
    block_type: Union[schemas.core.BlockType, "ClientBlockType"],
) -> UUID:
    """
    Stores the provided block type in the Prefect REST API database.

    If a block type with a matching slug is already saved, then the block type
    will be updated to match the passed in block type.

    Args:
        session: A database session.
        block_type: A block type object.

    Returns:
        The ID of the registered block type.
    """
    from prefect.server.models.block_types import (
        create_block_type,
        read_block_type_by_slug,
        update_block_type,
    )

    existing_block_type = await read_block_type_by_slug(
        session=session,
        block_type_slug=block_type.slug,
    )
    if existing_block_type is None:
        new_block_type = await create_block_type(
            session=session,
            block_type=block_type,
        )
        assert new_block_type is not None, f"Failed to create block type {block_type}"
        return new_block_type.id
    else:
        await update_block_type(
            session=session,
            block_type_id=existing_block_type.id,
            block_type=block_type,
        )
        return existing_block_type.id


async def _load_collection_blocks_data() -> Dict[str, Any]:
    """Loads blocks data for whitelisted collections."""
    import anyio

    async with await anyio.open_file(COLLECTIONS_BLOCKS_DATA_PATH, "r") as f:
        return json.loads(await f.read())


async def _register_registry_blocks(session: AsyncSession) -> None:
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


async def _register_collection_blocks(session: AsyncSession) -> None:
    """Registers blocks from whitelisted collections."""
    collections_blocks_data = await _load_collection_blocks_data()

    block_types = [
        block_type
        for collection in collections_blocks_data["collections"].values()
        for block_type in collection["block_types"].values()
    ]

    # due to schema reference dependencies, we need to register all block types first
    # and then register all block schemas
    block_schemas: dict[str, dict[str, Any]] = {}

    async with session.begin():
        for block_type in block_types:
            block_schema = block_type.pop("block_schema", None)
            if not block_schema:
                raise RuntimeError(
                    f"Block schema not found for block type {block_type.get('slug')!r}"
                )
            block_type_id = await register_block_type(
                session=session,
                block_type=schemas.core.BlockType.model_validate(block_type),
            )
            block_schema["block_type_id"] = block_type_id
            block_schemas[block_type["slug"]] = block_schema

    async with session.begin():
        for block_type_slug, block_schema in block_schemas.items():
            try:
                await register_block_schema(
                    session=session,
                    block_schema=schemas.core.BlockSchema.model_validate(block_schema),
                )
            except Exception:
                logger.exception(
                    f"Failed to register block schema for block type {block_type_slug}"
                )


async def run_block_auto_registration(session: AsyncSession) -> None:
    """
    Registers all blocks in the client block registry and any blocks from Prefect
    Collections that are configured for auto-registration.

    Args:
        session: A database session.
    """
    await _install_protected_system_blocks(session)
    await _register_registry_blocks(session)
    await _register_collection_blocks(session=session)
