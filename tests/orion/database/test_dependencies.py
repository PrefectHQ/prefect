from prefect.orion.database import dependencies
from prefect.orion.database.configurations import (
    AsyncPostgresConfiguration,
    AioSqliteConfiguration,
)
from prefect.orion.database.query_components import (
    AsyncPostgresQueryComponents,
    AioSqliteQueryComponents,
)


async def test_injecting_a_database_config():
    async with dependencies.temporary_db_config(AsyncPostgresConfiguration()):
        db = await dependencies.provide_database_interface()
        assert type(db.config) == AsyncPostgresConfiguration

    async with dependencies.temporary_db_config(AioSqliteConfiguration()):
        db = await dependencies.provide_database_interface()
        assert type(db.config) == AioSqliteConfiguration


async def test_injecting_query_components():
    async with dependencies.temporary_query_components(AsyncPostgresQueryComponents()):
        db = await dependencies.provide_database_interface()
        assert type(db.queries) == AsyncPostgresQueryComponents

    async with dependencies.temporary_query_components(AioSqliteQueryComponents()):
        db = await dependencies.provide_database_interface()
        assert type(db.queries) == AioSqliteQueryComponents
