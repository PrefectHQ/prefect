"""
Functions for interacting with block type ORM objects.
Intended for internal use by the Prefect REST API.
"""

import html
from typing import TYPE_CHECKING, Optional, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import schemas
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.database.orm_models import BlockSchema, BlockType

if TYPE_CHECKING:
    from prefect.client.schemas import BlockType as ClientBlockType
    from prefect.client.schemas.actions import BlockTypeUpdate as ClientBlockTypeUpdate


@db_injector
async def create_block_type(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_type: Union[schemas.core.BlockType, "ClientBlockType"],
    override: bool = False,
) -> "BlockType":
    """
    Create a new block type.

    Args:
        session: A database session
        block_type: a block type object

    Returns:
        block_type: an ORM block type model
    """
    # We take a shortcut in many unit tests and in block registration to pass client
    # models directly to this function.  We will support this by converting them to
    # the appropriate server model.
    if not isinstance(block_type, schemas.core.BlockType):
        block_type = schemas.core.BlockType.model_validate(
            block_type.model_dump(mode="json")
        )

    insert_values = block_type.model_dump_for_orm(
        exclude_unset=False, exclude={"created", "updated", "id"}
    )
    if insert_values.get("description") is not None:
        insert_values["description"] = html.escape(
            insert_values["description"], quote=False
        )
    if insert_values.get("code_example") is not None:
        insert_values["code_example"] = html.escape(
            insert_values["code_example"], quote=False
        )
    insert_stmt = db.insert(BlockType).values(**insert_values)
    if override:
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=db.block_type_unique_upsert_columns,
            set_=insert_values,
        )
    await session.execute(insert_stmt)

    query = (
        sa.select(BlockType)
        .where(
            sa.and_(
                BlockType.name == insert_values["name"],
            )
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


async def read_block_type(
    session: AsyncSession,
    block_type_id: UUID,
):
    """
    Reads a block type by id.

    Args:
        session: A database session
        block_type_id: a block_type id

    Returns:
        BlockType: an ORM block type model
    """
    return await session.get(BlockType, block_type_id)


async def read_block_type_by_slug(session: AsyncSession, block_type_slug: str):
    """
    Reads a block type by slug.

    Args:
        session: A database session
        block_type_slug: a block type slug

    Returns:
        BlockType: an ORM block type model

    """
    result = await session.execute(
        sa.select(BlockType).where(BlockType.slug == block_type_slug)
    )
    return result.scalar()


async def read_block_types(
    session: AsyncSession,
    block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """
    Reads block types with an optional limit and offset

    Args:

    Returns:
        List[BlockType]: List of
    """
    query = sa.select(BlockType).order_by(BlockType.name)

    if block_type_filter is not None:
        query = query.where(block_type_filter.as_sql_filter())

    if block_schema_filter is not None:
        exists_clause = sa.select(BlockSchema).where(
            BlockSchema.block_type_id == BlockType.id,
            block_schema_filter.as_sql_filter(),
        )
        query = query.where(exists_clause.exists())

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def update_block_type(
    session: AsyncSession,
    block_type_id: str,
    block_type: Union[schemas.actions.BlockTypeUpdate, "ClientBlockTypeUpdate"],
) -> bool:
    """
    Update a block type by id.

    Args:
        session: A database session
        block_type_id: Data to update block type with
        block_type: A block type id

    Returns:
        bool: True if the block type was updated
    """

    # We take a shortcut in many unit tests and in block registration to pass client
    # models directly to this function.  We will support this by converting them to
    # the appropriate server model.
    if not isinstance(block_type, schemas.actions.BlockTypeUpdate):
        block_type = schemas.actions.BlockTypeUpdate.model_validate(
            block_type.model_dump(
                mode="json",
                exclude={"id", "created", "updated", "name", "slug", "is_protected"},
            )
        )

    update_statement = (
        sa.update(BlockType)
        .where(BlockType.id == block_type_id)
        .values(**block_type.model_dump_for_orm(exclude_unset=True, exclude={"id"}))
    )
    result = await session.execute(update_statement)
    return result.rowcount > 0


async def delete_block_type(session: AsyncSession, block_type_id: str):
    """
    Delete a block type by id.

    Args:
        session: A database session
        block_type_id: A block type id

    Returns:
        bool: True if the block type was updated
    """

    result = await session.execute(
        sa.delete(BlockType).where(BlockType.id == block_type_id)
    )
    return result.rowcount > 0
