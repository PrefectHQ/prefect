"""
Functions for interacting with block ORM objects.
Intended for internal use by the Orion API.
"""
from uuid import UUID

import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_block(
    session: sa.orm.Session,
    block: schemas.core.Block,
    db: OrionDBInterface,
):

    orm_block = db.Block(
        name=block.name,
        block_spec_id=block.block_spec_id,
    )

    # encrypt the data and store on the block
    await orm_block.encrypt_data(session=session, data=block.data)

    # add the block to the session and flush
    session.add(orm_block)
    await session.flush()

    # reload the block in order to load the associated block spec relationship
    return await read_block_by_id(session=session, block_id=orm_block.id)


@inject_db
async def read_block_by_id(
    session: sa.orm.Session,
    block_id: UUID,
    db: OrionDBInterface,
):
    query = (
        sa.select(db.Block)
        .where(db.Block.id == block_id)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    block = result.scalar()
    return block


@inject_db
async def read_block_by_name(
    session: sa.orm.Session,
    name: str,
    block_spec_name: str,
    db: OrionDBInterface,
    block_spec_version: str = None,
):
    """
    Read a block with the given name and block spec name. If a block spec version
    is provided, it is matched as well, otherwise the latest matching version is returned.
    """
    where_clause = [
        db.Block.name == name,
        db.BlockSpec.name == block_spec_name,
    ]
    if block_spec_version is not None:
        where_clause.append(db.BlockSpec.version == block_spec_version)

    query = (
        sa.select(db.Block)
        .join(db.BlockSpec, db.BlockSpec.id == db.Block.block_spec_id)
        .where(sa.and_(*where_clause))
        .order_by(db.BlockSpec.version.desc())
        .limit(1)
    )
    result = await session.execute(query)
    block = result.scalar()
    return block


@inject_db
async def read_blocks(
    session: sa.orm.Session,
    db: OrionDBInterface,
    block_spec_type: str = None,
    offset: int = None,
    limit: int = None,
):
    """
    Read blocks with an optional limit and offset
    """

    query = (
        sa.select(db.Block)
        .join(db.BlockSpec, db.BlockSpec.id == db.Block.block_spec_id)
        .order_by(db.BlockSpec.name, db.BlockSpec.version.desc(), db.Block.name)
    )

    if block_spec_type is not None:
        query = query.where(db.BlockSpec.type == block_spec_type)

    if offset is not None:
        query = query.offset(offset)

    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def delete_block(
    session: sa.orm.Session,
    block_id: UUID,
    db: OrionDBInterface,
) -> bool:

    query = sa.delete(db.Block).where(db.Block.id == block_id)
    result = await session.execute(query)
    return result.rowcount > 0


@inject_db
async def update_block(
    session: sa.orm.Session,
    block_id: UUID,
    block: schemas.actions.BlockUpdate,
    db: OrionDBInterface,
) -> bool:

    block = await session.get(db.Block, block_id)
    if not block:
        return False

    update_values = block.dict(shallow=True, exclude_unset=True)
    if "data" in update_values:
        block.encrypt_data(session=session, data=update_values["data"])
    if "name" in update_values:
        block.name = update_values["name"]

    await session.flush()

    return True


@inject_db
async def get_default_storage_block(session: sa.orm.Session, db: OrionDBInterface):
    query = (
        sa.select(db.Block)
        .where(db.Block.is_default_storage_block.is_(True))
        .limit(1)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(query)
    block = result.scalar()
    return block


@inject_db
async def set_default_storage_block(
    session: sa.orm.Session, block_id: UUID, db: OrionDBInterface
):
    block = await read_block_by_id(session=session, block_id=block_id)
    if not block:
        raise ValueError("Block not found")
    elif block.block_spec.type != "STORAGE":
        raise ValueError("Block spec type must be STORAGE")

    await clear_default_storage_block(session=session)
    block.is_default_storage_block = True
    await session.flush()


@inject_db
async def clear_default_storage_block(session: sa.orm.Session, db: OrionDBInterface):
    await session.execute(
        sa.update(db.Block)
        .where(db.Block.is_default_storage_block.is_(True))
        .values(is_default_storage_block=False)
    )
    await session.flush()
