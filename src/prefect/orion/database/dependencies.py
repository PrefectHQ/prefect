"""
Injected models dependencies
"""

from contextlib import asynccontextmanager
from functools import wraps


MODELS_DEPENDENCIES = {
    "database_config": None,
    "query_components": None,
    "orm": None,
}


def provide_database_interface():
    from prefect.orion.database.interface import OrionDBInterface

    database_config = MODELS_DEPENDENCIES.get("database_config")
    query_components = MODELS_DEPENDENCIES.get("query_components")
    orm = MODELS_DEPENDENCIES.get("orm")

    if database_config is None:
        from prefect import settings
        from prefect.orion.database.configurations import (
            AsyncPostgresConfiguration,
            AioSqliteConfiguration,
        )
        from prefect.orion.utilities.database import get_dialect

        dialect = get_dialect()
        connection_url = settings.orion.database.connection_url.get_secret_value()

        if dialect.name == "postgresql":
            database_config = AsyncPostgresConfiguration(connection_url=connection_url)
        elif dialect.name == "sqlite":
            database_config = AioSqliteConfiguration(connection_url=connection_url)
        else:
            raise ValueError(
                f"Unable to infer database configuration from provided dialect. Got dialect name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["database_config"] = database_config

    if query_components is None:
        from prefect.orion.database.query_components import (
            AsyncPostgresQueryComponents,
            AioSqliteQueryComponents,
        )
        from prefect.orion.utilities.database import get_dialect

        dialect = get_dialect()

        if dialect.name == "postgresql":
            query_components = AsyncPostgresQueryComponents()
        elif dialect.name == "sqlite":
            query_components = AioSqliteQueryComponents()
        else:
            raise ValueError(
                f"Unable to infer query components from provided dialect. Got dialect name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["query_components"] = query_components

    if orm is None:
        from prefect.orion.database.orm_models import (
            AsyncPostgresORMConfiguration,
            AioSqliteORMConfiguration,
        )
        from prefect.orion.utilities.database import get_dialect

        dialect = get_dialect()

        if dialect.name == "postgresql":
            orm = AsyncPostgresORMConfiguration()
        elif dialect.name == "sqlite":
            orm = AioSqliteORMConfiguration()
        else:
            raise ValueError(
                f"Unable to infer orm configuration from provided dialect. Got dialect name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["orm"] = orm

    return OrionDBInterface(
        database_config=database_config,
        query_components=query_components,
        orm=orm,
    )


def inject_db(fn):
    """
    Simple helper to provide a database interface to a function.

    The decorated function _must_ take a `db` kwarg and if a db is passed
    when called it will be used instead of creating a new one.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "db" not in kwargs or kwargs["db"] is None:
            kwargs["db"] = provide_database_interface()
        return fn(*args, **kwargs)

    return wrapper


@asynccontextmanager
async def temporary_database_config(tmp_database_config):
    starting_config = MODELS_DEPENDENCIES["database_config"]
    try:
        MODELS_DEPENDENCIES["database_config"] = tmp_database_config
        yield
    finally:
        MODELS_DEPENDENCIES["database_config"] = starting_config


@asynccontextmanager
async def temporary_query_components(tmp_queries):
    starting_queries = MODELS_DEPENDENCIES["query_components"]
    try:
        MODELS_DEPENDENCIES["query_components"] = tmp_queries
        yield
    finally:
        MODELS_DEPENDENCIES["query_components"] = starting_queries


@asynccontextmanager
async def temporary_orm_config(tmp_orm_config):
    starting_orm_config = MODELS_DEPENDENCIES["orm"]
    try:
        MODELS_DEPENDENCIES["orm"] = tmp_orm_config
        yield
    finally:
        MODELS_DEPENDENCIES["orm"] = starting_orm_config
