"""
Functions for interacting with block type ORM objects.
Intended for internal use by the Prefect REST API.
"""

import html
from typing import TYPE_CHECKING, Optional, Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import schemas
from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.database.orm_models import BlockType

if TYPE_CHECKING:
    from prefect.client.schemas import BlockType as ClientBlockType
    from prefect.client.schemas.actions import BlockTypeUpdate as ClientBlockTypeUpdate


@db_injector
async def create_block_type(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_type: Union[schemas.core.BlockType, "ClientBlockType"],
    override: bool = False,
) -> Union[BlockType, None]:
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
    insert_stmt = db.queries.insert(db.BlockType).values(**insert_values)
    if override:
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=db.orm.block_type_unique_upsert_columns,
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


@db_injector
async def read_block_type(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_type_id: UUID,
) -> Union[BlockType, None]:
    """
    Reads a block type by id.

    Args:
        session: A database session
        block_type_id: a block_type id

    Returns:
        BlockType: an ORM block type model
    """
    return await session.get(db.BlockType, block_type_id)


@db_injector
async def read_block_type_by_slug(
    db: PrefectDBInterface, session: AsyncSession, block_type_slug: str
) -> Union[BlockType, None]:
    """
    Reads a block type by slug.

    Args:
        session: A database session
        block_type_slug: a block type slug

    Returns:
        BlockType: an ORM block type model

    """
    result = await session.execute(
        sa.select(db.BlockType).where(db.BlockType.slug == block_type_slug)
    )
    return result.scalar()


@db_injector
async def read_block_types(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_type_filter: Optional[schemas.filters.BlockTypeFilter] = None,
    block_schema_filter: Optional[schemas.filters.BlockSchemaFilter] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Sequence[BlockType]:
    """
    Reads block types with an optional limit and offset

    Args:

    Returns:
        List[BlockType]: List of
    """
    query = sa.select(db.BlockType).order_by(db.BlockType.name)

    if block_type_filter is not None:
        query = query.where(block_type_filter.as_sql_filter())

    if block_schema_filter is not None:
        exists_clause = sa.select(db.BlockSchema).where(
            db.BlockSchema.block_type_id == db.BlockType.id,
            block_schema_filter.as_sql_filter(),
        )
        query = query.where(exists_clause.exists())

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def update_block_type(
    db: PrefectDBInterface,
    session: AsyncSession,
    block_type_id: Union[str, UUID],
    block_type: Union[
        schemas.actions.BlockTypeUpdate,
        schemas.core.BlockType,
        "ClientBlockTypeUpdate",
        "ClientBlockType",
    ],
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
        sa.update(db.BlockType)
        .where(db.BlockType.id == block_type_id)
        .values(**block_type.model_dump_for_orm(exclude_unset=True, exclude={"id"}))
    )
    result = await session.execute(update_statement)
    return result.rowcount > 0


@db_injector
async def delete_block_type(
    db: PrefectDBInterface, session: AsyncSession, block_type_id: str
) -> bool:
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
