"""
Injected models dependencies
"""

from contextlib import asynccontextmanager
from functools import wraps


MODELS_DEPENDENCIES = {
    "connection_configuration": None,
    "query_components": None,
    "orm": None,
}


def provide_database_interface():
    from prefect.orion.database.interface import OrionDBInterface

    connection_config = MODELS_DEPENDENCIES.get("connection_configuration")
    query_components = MODELS_DEPENDENCIES.get("query_components")
    orm = MODELS_DEPENDENCIES.get("orm")

    if connection_config is None:
        from prefect import settings
        from prefect.orion.database.connections import (
            AsyncPostgresConnectionConfiguration,
            AioSqliteConnectionConfiguration,
        )
        from prefect.orion.utilities.database import get_dialect

        dialect = get_dialect()
        connection_url = settings.orion.database.connection_url.get_secret_value()

        if dialect.name == "postgresql":
            connection_config = AsyncPostgresConnectionConfiguration(
                connection_url=connection_url
            )
        elif dialect.name == "sqlite":
            connection_config = AioSqliteConnectionConfiguration(
                connection_url=connection_url
            )
        else:
            raise ValueError(
                f"Unable to infer database configuration from provided dialect. Got dialect name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["connection_configuration"] = connection_config

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
        connection_config=connection_config,
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
async def temporary_connection_config(tmp_connection_config):
    starting_config = MODELS_DEPENDENCIES["connection_configuration"]
    try:
        MODELS_DEPENDENCIES["connection_configuration"] = tmp_connection_config
        yield
    finally:
        MODELS_DEPENDENCIES["connection_configuration"] = starting_config


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
