from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import schemas
from prefect.server.database import PrefectDBInterface, db_injector, orm_models

SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY = "server-default-result-storage"


@db_injector
async def write_configuration(
    db: PrefectDBInterface,
    session: AsyncSession,
    configuration: schemas.core.Configuration,
) -> orm_models.Configuration:
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
    db.queries.clear_configuration_value_cache_for_key(key=configuration.key)

    return existing_configuration


@db_injector
async def delete_configuration(
    db: PrefectDBInterface,
    session: AsyncSession,
    key: str,
) -> bool:
    query = sa.delete(db.Configuration).where(db.Configuration.key == key)
    result = await session.execute(query)
    db.queries.clear_configuration_value_cache_for_key(key=key)
    return result.rowcount > 0


@db_injector
async def read_configuration(
    db: PrefectDBInterface,
    session: AsyncSession,
    key: str,
) -> Optional[schemas.core.Configuration]:
    value = await db.queries.read_configuration_value(session=session, key=key)
    return (
        schemas.core.Configuration(key=key, value=value) if value is not None else None
    )


async def write_server_default_result_storage(
    session: AsyncSession,
    configuration: schemas.core.ServerDefaultResultStorage,
) -> orm_models.Configuration:
    return await write_configuration(
        session=session,
        configuration=schemas.core.Configuration(
            key=SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
            value=configuration.model_dump(mode="json"),
        ),
    )


async def read_server_default_result_storage(
    session: AsyncSession,
) -> schemas.core.ServerDefaultResultStorage:
    configuration = await read_configuration(
        session=session,
        key=SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
    )
    if configuration is None:
        return schemas.core.ServerDefaultResultStorage()
    return schemas.core.ServerDefaultResultStorage.model_validate(configuration.value)


async def clear_server_default_result_storage(session: AsyncSession) -> bool:
    return await delete_configuration(
        session=session,
        key=SERVER_DEFAULT_RESULT_STORAGE_CONFIGURATION_KEY,
    )
