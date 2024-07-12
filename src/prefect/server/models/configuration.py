from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import schemas
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface


@db_injector
async def write_configuration(
    db: PrefectDBInterface,
    session: AsyncSession,
    configuration: schemas.core.Configuration,
) -> orm_models.Configuration:
    # first see if the key already exists
    query = sa.select(orm_models.Configuration).where(
        orm_models.Configuration.key == configuration.key
    )
    result = await session.execute(query)  # type: ignore
    existing_configuration = result.scalar()
    # if it exists, update its value
    if existing_configuration:
        existing_configuration.value = configuration.value
    # else create a new ORM object
    else:
        existing_configuration = orm_models.Configuration(
            key=configuration.key, value=configuration.value
        )
    session.add(existing_configuration)
    await session.flush()

    # clear the cache for this key after writing a value
    db.clear_configuration_value_cache_for_key(key=configuration.key)

    return existing_configuration


@db_injector
async def read_configuration(
    db: PrefectDBInterface,
    session: AsyncSession,
    key: str,
) -> Optional[schemas.core.Configuration]:
    value = await db.read_configuration_value(session=session, key=key)
    return (
        schemas.core.Configuration(key=key, value=value) if value is not None else None
    )
