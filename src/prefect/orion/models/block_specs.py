"""
Functions for interacting with block schema ORM objects.
Intended for internal use by the Orion API.
"""
import hashlib
import json
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.utilities.hashing import hash_objects, stable_hash


@inject_db
async def create_block_schema(
    session: sa.orm.Session,
    block_schema: schemas.actions.BlockSchemaCreate,
    db: OrionDBInterface,
    override: bool = False,
):
    """
    Create a new block schema.

    Args:
        session: A database session
        block_schema: a block schema object

    Returns:
        block_schema: an ORM block schema model
    """
    insert_values = block_schema.dict(
        shallow=True,
        exclude_unset=False,
        exclude={"block_type", "id", "created", "updated"},
    )
    insert_values[
        "checksum"
    ] = f"sha256:{hash_objects(insert_values['fields'], hash_algo=hashlib.sha256)}"
    insert_stmt = (await db.insert(db.BlockSchema)).values(**insert_values)
    if override:
        insert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=db.block_schema_unique_upsert_columns,
            set_=insert_values,
        )
    await session.execute(insert_stmt)

    query = (
        sa.select(db.BlockSchema)
        .where(
            db.BlockSchema.checksum == insert_values["checksum"],
        )
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def delete_block_schema(
    session: sa.orm.Session, block_schema_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a block schema by id.

    Args:
        session: A database session
        block_schema_id: a block schema id

    Returns:
        bool: whether or not the block schema was deleted
    """

    result = await session.execute(
        delete(db.BlockSchema).where(db.BlockSchema.id == block_schema_id)
    )
    return result.rowcount > 0


@inject_db
async def read_block_schema(
    session: sa.orm.Session,
    block_schema_id: UUID,
    db: OrionDBInterface,
):
    """
    Reads a block schema by id.

    Args:
        session: A database session
        block_schema_id: a block_schema id

    Returns:
        db.Blockschema: the block_schema
    """
    return await session.get(db.BlockSchema, block_schema_id)


@inject_db
async def read_block_schemas(
    session: sa.orm.Session,
    db: OrionDBInterface,
    block_schema_type: Optional[str] = None,
    block_type_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    """
    Reads block schemas, optionally filtered by type or name.

    Args:
        session: A database session
        block_schema_type: the block schema type
        block_type_id: the ID of the corresponding block type
        limit (int): query limit
        offset (int): query offset

    Returns:
        List[db.Blockschema]: the block_schemas
    """
    query = select(db.BlockSchema).order_by(
        db.BlockSchema.block_type_id, db.BlockSchema.created
    )
    if block_schema_type is not None:
        query = query.filter_by(type=block_schema_type)
    if block_type_id is not None:
        query = query.filter_by(block_type_id=block_type_id)
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def read_block_schema_by_checksum(
    session: sa.orm.Session,
    checksum: str,
    db: OrionDBInterface,
):
    """
    Reads a block_schema by checksum.

    Args:
        session: A database session
        checksum: a block_schema checksum

    Returns:
        db.Blockschema: the block_schema
    """

    result = await session.execute(select(db.BlockSchema).filter_by(checksum=checksum))
    return result.scalar()
