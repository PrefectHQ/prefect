"""
Injected models dependencies
"""

MODELS_DEPENDENCIES = {
    "database_configuration": lambda: None,
}

CURRENT = {"config": None}


async def get_database_configuration():
    # provided_config = MODELS_DEPENDENCIES.get("database_configuration")()
    provided_config = CURRENT.get("config")

    if provided_config is None:
        from prefect.orion.utilities.database import AsyncPostgresConfiguration

        provided_config = AsyncPostgresConfiguration()
        CURRENT["config"] = provided_config

    return provided_config
