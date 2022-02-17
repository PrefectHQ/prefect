import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_configuration(
    session: sa.orm.Session,
    configuration: schemas.core.Configuration,
    db: OrionDBInterface,
):
    insert_values = configuration.dict(shallow=True, exclude_unset=True)
    key = insert_values["key"]

    insert_stmt = (await db.insert(db.Configuration)).values(**insert_values)

    await session.execute(insert_stmt)
    query = (
        sa.select(db.Configuration)
        .where(db.Configuration.key == key)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_configuration_by_key(
    session: sa.orm.Session,
    key: str,
    db: OrionDBInterface,
):
    query = sa.select(db.Configuration).where(db.Configuration.key == key)

    result = await session.execute(query)
    return result.scalar()
