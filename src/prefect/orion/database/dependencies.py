"""
Injected models dependencies
"""

from functools import wraps


MODELS_DEPENDENCIES = {
    "database_configuration": lambda: None,
}

CURRENT = {"config": None}


async def get_database_configuration():
    # provided_config = MODELS_DEPENDENCIES.get("database_configuration")()
    provided_config = CURRENT.get("config")

    if provided_config is None:
        from prefect.orion.database.configurations import AsyncPostgresConfiguration

        provided_config = AsyncPostgresConfiguration()
        CURRENT["config"] = provided_config

    return provided_config


def inject_db_config(fn):
    """
    Simple helper to provide a database configuration to a asynchronous function.

    The decorated function _must_ take a `db_config` kwarg and if a config is passed when
    called it will be used instead of creating a new one.
    """

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        if "db_config" in kwargs and kwargs["db_config"] is not None:
            return await fn(*args, **kwargs)
        else:
            kwargs["db_config"] = await get_database_configuration()
            return await fn(*args, **kwargs)

    return wrapper
