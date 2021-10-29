"""
Injected models dependencies
"""

from functools import wraps


MODELS_DEPENDENCIES = {"database_configuration": None, "database_interface": None}


async def provide_database_interface():
    from prefect.orion.database.configurations import OrionDBInterface

    provided_config = MODELS_DEPENDENCIES.get("database_configuration")

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

        # TODO - clean this up
        MODELS_DEPENDENCIES["database_configuration"] = provided_config
        MODELS_DEPENDENCIES["database_interface"] = OrionDBInterface(
            db_config=provided_config
        )

    return MODELS_DEPENDENCIES["database_interface"]


def inject_db_interface(fn):
    """
    Simple helper to provide a database configuration to a asynchronous function.

    The decorated function _must_ take a `db_config` kwarg and if a config is passed when
    called it will be used instead of creating a new one.
    """

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        if "db_interface" in kwargs and kwargs["db_interface"] is not None:
            return await fn(*args, **kwargs)
        else:
            kwargs["db_interface"] = await provide_database_interface()
            return await fn(*args, **kwargs)

    return wrapper
