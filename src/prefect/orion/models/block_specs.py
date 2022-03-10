"""
Functions for interacting with block spec ORM objects.
Intended for internal use by the Orion API.
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_block_spec(
    session: sa.orm.Session,
    block_spec: schemas.core.BlockSpec,
    db: OrionDBInterface,
    override: bool = False,
):
    """
    Create a new block spec.

    Args:
        session: A database session
        block_spec: a block spec object

    Returns:
        block_spec: an ORM block spec model
    """
    insert_values = block_spec.dict(
        shallow=True, exclude_unset=False, exclude={"created", "updated", "id"}
    )
    insert_stmt = (await db.insert(db.BlockSpec)).values(**insert_values)
    if override:
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=db.block_spec_unique_upsert_columns,
            set_=insert_values,
        )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.BlockSpec)
        .where(
            sa.and_(
                db.BlockSpec.name == insert_values["name"],
                db.BlockSpec.version == insert_values["version"],
            )
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def delete_block_spec(
    session: sa.orm.Session, block_spec_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a block spec by id.

    Args:
        session: A database session
        block_spec_id: a block spec id

    Returns:
        bool: whether or not the block spec was deleted
    """

    result = await session.execute(
        delete(db.BlockSpec).where(db.BlockSpec.id == block_spec_id)
    )
    return result.rowcount > 0


@inject_db
async def read_block_spec(
    session: sa.orm.Session,
    block_spec_id: UUID,
    db: OrionDBInterface,
):
    """
    Reads a block spec by id.

    Args:
        session: A database session
        block_spec_id: a block_spec id

    Returns:
        db.BlockSpec: the block_spec
    """
    return await session.get(db.BlockSpec, block_spec_id)


@inject_db
async def read_block_specs(
    session: sa.orm.Session,
    db: OrionDBInterface,
    block_spec_type: str = None,
    name: str = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """
    Reads block specs, optionally filtered by type or name.

    Args:
        session: A database session
        block_spec_type: the block spec type
        name: the block spec name
        limit (int): query limit
        offset (int): query offset

    Returns:
        List[db.BlockSpec]: the block_specs
    """
    query = select(db.BlockSpec).order_by(db.BlockSpec.name, db.BlockSpec.created)
    if block_spec_type is not None:
        query = query.filter_by(type=block_spec_type)
    if name is not None:
        query = query.filter_by(name=name)
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def read_block_spec_by_name_and_version(
    session: sa.orm.Session,
    name: str,
    version: str,
    db: OrionDBInterface,
):
    """
    Reads a block_spec by name.

    Args:
        session: A database session
        name: a block_spec name

    Returns:
        db.BlockSpec: the block_spec
    """

    result = await session.execute(
        select(db.BlockSpec).filter_by(name=name, version=version)
    )
    return result.scalar()
