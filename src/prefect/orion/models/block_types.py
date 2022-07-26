"""
Functions for interacting with block type ORM objects.
Intended for internal use by the Orion API.
"""
import html
from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.database.orm_models import ORMBlockType


@inject_db
async def create_block_type(
    session: sa.orm.Session,
    block_type: schemas.core.BlockType,
    db: OrionDBInterface,
    override: bool = False,
) -> ORMBlockType:
    """
    Create a new block type.

    Args:
        session: A database session
        block_type: a block type object

    Returns:
        block_type: an ORM block type model
    """
    insert_values = block_type.dict(
        shallow=True, exclude_unset=False, exclude={"created", "updated", "id"}
    )
    if insert_values.get("description") is not None:
        insert_values["description"] = html.escape(
            insert_values["description"], quote=False
        )
    if insert_values.get("code_example") is not None:
        insert_values["code_example"] = html.escape(
            insert_values["code_example"], quote=False
        )
    insert_stmt = (await db.insert(db.BlockType)).values(**insert_values)
    if override:
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=db.block_type_unique_upsert_columns,
            set_=insert_values,
        )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.BlockType)
        .where(
            sa.and_(
                db.BlockType.name == insert_values["name"],
            )
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_block_type(
    session: sa.orm.Session,
    block_type_id: UUID,
    db: OrionDBInterface,
):
    """
    Reads a block type by id.

    Args:
        session: A database session
        block_type_id: a block_type id

    Returns:
        db.BlockType: an ORM block type model
    """
    return await session.get(db.BlockType, block_type_id)


@inject_db
async def read_block_type_by_slug(
    session: sa.orm.Session, block_type_slug: str, db: OrionDBInterface
):
    """
    Reads a block type by slug.

    Args:
        session: A database session
        block_type_slug: a block type slug

    Returns:
        db.BlockType: an ORM block type model

    """
    result = await session.execute(
        sa.select(db.BlockType).where(db.BlockType.slug == block_type_slug)
    )
    return result.scalar()


@inject_db
async def read_block_types(
    session: sa.orm.Session,
    db: OrionDBInterface,
    block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """
    Reads block types with an optional limit and offset

    Args:

    Returns:
        List[db.BlockType]: List of
    """
    query = sa.select(db.BlockType).order_by(db.BlockType.name)

    if block_type_filter is not None:
        query = query.where(block_type_filter.as_sql_filter(db))

    if block_schema_filter is not None:
        exists_clause = sa.select(db.BlockSchema).where(
            db.BlockSchema.block_type_id == db.BlockType.id,
            block_schema_filter.as_sql_filter(db),
        )
        query = query.where(exists_clause.exists())

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_block_type(
    session: sa.orm.Session,
    block_type_id: str,
    block_type: schemas.actions.BlockTypeUpdate,
    db: OrionDBInterface,
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
    update_statement = (
        sa.update(db.BlockType)
        .where(db.BlockType.id == block_type_id)
        .values(**block_type.dict(shallow=True, exclude_unset=True))
    )
    result = await session.execute(update_statement)
    return result.rowcount > 0


@inject_db
async def delete_block_type(
    session: sa.orm.Session, block_type_id: str, db: OrionDBInterface
):
    """
    Delete a block type by id.

    Args:
        session: A database session
        block_type_id: A block type id

    Returns:
        bool: True if the block type was updated
    """

    result = await session.execute(
        sa.delete(db.BlockType).where(db.BlockType.id == block_type_id)
    )
    return result.rowcount > 0
