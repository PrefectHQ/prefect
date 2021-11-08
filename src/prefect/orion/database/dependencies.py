"""
Injected models dependencies
"""

from contextlib import asynccontextmanager
from functools import wraps


MODELS_DEPENDENCIES = {
    "database_configuration": None,
    "query_components": None,
}


async def provide_database_interface():
    from prefect.orion.database.interface import OrionDBInterface

    provided_config = MODELS_DEPENDENCIES.get("database_configuration")
    query_components = MODELS_DEPENDENCIES.get("query_components")

    if provided_config is None:
        from prefect.orion.database.configurations import (
            AsyncPostgresConfiguration,
            AioSqliteConfiguration,
        )
        from prefect.orion.utilities.database import get_dialect

        dialect = get_dialect()

        if dialect.name == "postgresql":
            provided_config = AsyncPostgresConfiguration()
        elif dialect.name == "sqlite":
            provided_config = AioSqliteConfiguration()
        else:
            raise ValueError(
                f"Unable to infer database configuration from provided dialect. Got dialect name {dialect.name!r}"
            )

        MODELS_DEPENDENCIES["database_configuration"] = provided_config

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

    return OrionDBInterface(
        db_config=provided_config,
        query_components=query_components,
    )


def inject_db(fn):
    """
    Simple helper to provide a database configuration to an asynchronous function.

    The decorated function _must_ take a `db_config` kwarg and if a config is passed
    when called it will be used instead of creating a new one.
    """

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        if "db" in kwargs and kwargs["db"] is not None:
            return await fn(*args, **kwargs)
        else:
            kwargs["db"] = await provide_database_interface()
            return await fn(*args, **kwargs)

    return wrapper


@asynccontextmanager
async def temporary_db_config(tmp_config):
    starting_config = MODELS_DEPENDENCIES["database_configuration"]
    try:
        MODELS_DEPENDENCIES["database_configuration"] = tmp_config
        yield
    finally:
        MODELS_DEPENDENCIES["database_configuration"] = starting_config


@asynccontextmanager
async def temporary_query_components(tmp_queries):
    starting_queries = MODELS_DEPENDENCIES["query_components"]
    try:
        MODELS_DEPENDENCIES["query_components"] = tmp_queries
        yield
    finally:
        MODELS_DEPENDENCIES["query_components"] = starting_queries
