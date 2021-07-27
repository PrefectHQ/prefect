import asyncio
import prefect.orion.utilities
import prefect.orion.schemas
import prefect.orion.models
import prefect.orion.api

from prefect.orion.utilities.settings import Settings
from prefect.orion.utilities import database as _database

# if the orion database engine is in-memory, populate it
if (
    _database.engine.url.get_backend_name() == "sqlite"
    and _database.engine.url.database == ":memory:"
):
    asyncio.run(_database.create_database_objects())
