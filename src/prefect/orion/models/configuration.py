from typing import Optional

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
    query = sa.select(db.Configuration).where(db.Configuration.key == configuration.key)
    result = await session.execute(query)  # type: ignore
    existing_configuration = result.scalar()
    # if it exists, update its value
    if existing_configuration:
        existing_configuration.value = configuration.value
    # else create a new ORM object
    else:
        existing_configuration = db.Configuration(
            key=configuration.key, value=configuration.value
        )
    session.add(existing_configuration)
    await session.flush()

    # clear the cache for this key after writing a value
    db.clear_configuration_value_cache_for_key(key=configuration.key)

    return existing_configuration


@inject_db
async def read_configuration(
    session: sa.orm.Session,
    key: str,
    db: OrionDBInterface,
) -> Optional[schemas.core.Configuration]:
    value = await db.read_configuration_value(session=session, key=key)
    return (
        schemas.core.Configuration(key=key, value=value) if value is not None else None
    )
