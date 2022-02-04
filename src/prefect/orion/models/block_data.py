"""
Functions for interacting with block data ORM objects.
Intended for internal use by the Orion API.
"""
import pendulum
import sqlalchemy as sa
from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_block_data(
    session: sa.orm.Session,
    block_data: schemas.core.BlockData,
    db: OrionDBInterface,
):
    insert_values = block_data.dict(shallow=True, exclude_unset=True)
    blockname = insert_values["name"]

    # set `updated` manually
    # known limitation of `on_conflict_do_update`, will not use `Column.onupdate`
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#the-set-clause
    block_data.updated = pendulum.now("UTC")
    insert_stmt = (await db.insert(db.BlockData)).values(**insert_values)

    await session.execute(insert_stmt)
    query = (
        sa.select(db.BlockData)
        .where(db.BlockData.name == blockname)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_block_data_by_name(
    session: sa.orm.Session,
    name: str,
    db: OrionDBInterface,
):
    query = sa.select(db.BlockData).where(db.BlockData.name == name).with_for_update()

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def delete_block_data_by_name(
    session: sa.orm.Session,
    name: str,
    db: OrionDBInterface,
) -> bool:

    query = sa.delete(db.BlockData).where(db.BlockData.name == name)

    result = await session.execute(query)
    return result.rowcount > 0
