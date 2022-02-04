"""
Functions for interacting with block data ORM objects.
Intended for internal use by the Orion API.
"""


@inject_db
async def create_block_data(
    session: sa.orm.Session,
    block_data: schemas.core.BlockData,
    db: OrionDBInterface,
):
    insert_values = block_data.dict(shallow=True, exclude_unset=True)

    # set `updated` manually
    # known limitation of `on_conflict_do_update`, will not use `Column.onupdate`
    # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#the-set-clause
    block_data.updated = pendulum.now("UTC")
    insert_stmt = (await db.insert(db.BlockData)).values(**insert_values)

    await session.execute(insert_stmt)


@inject_db
async def delete_block_data_by_name(
    session: sa.orm.Session,
    name: str,
    db: OrionDBInterface,
) -> bool:

    query = sa.delete(db.BlockData).where(db.BlockData.name == name)

    result = await session.execute(query)
    return result.rowcount > 0
