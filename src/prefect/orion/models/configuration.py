import sqlalchemy as sa

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def write_configuration(
    session: sa.orm.Session,
    configuration: schemas.core.Configuration,
    db: OrionDBInterface,
):
    # first see if the key already exists
    orm_configuration = await read_configuration(session=session, key=configuration.key)
    # if it exists, update its value
    if orm_configuration:
        orm_configuration.value = configuration.value
    # else create a new ORM object
    else:
        orm_configuration = db.Configuration(
            key=configuration.key, value=configuration.value
        )
    session.add(orm_configuration)
    await session.flush()
    return orm_configuration


@inject_db
async def read_configuration(
    session: sa.orm.Session,
    key: str,
    db: OrionDBInterface,
):
    query = sa.select(db.Configuration).where(db.Configuration.key == key)
    result = await session.execute(query)
    return result.scalar()
