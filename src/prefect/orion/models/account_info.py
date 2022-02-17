import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_account_info(
    session: sa.orm.Session,
    account_info: schemas.core.AccountInfo,
    db: OrionDBInterface,
):
    insert_values = account_info.dict(shallow=True, exclude_unset=True)
    key = insert_values["key"]

    insert_stmt = (await db.insert(db.AccountInfo)).values(**insert_values)

    await session.execute(insert_stmt)
    query = (
        sa.select(db.AccountInfo)
        .where(db.AccountInfo.key == key)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_account_info_by_key(
    session: sa.orm.Session,
    key: str,
    db: OrionDBInterface,
):
    query = sa.select(db.AccountInfo).where(db.AccountInfo.key == key)

    result = await session.execute(query)
    return result.scalar()
