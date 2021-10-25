"""
Utilities for injecting FastAPI dependencies.
"""

from prefect import settings
from prefect.orion.models.dependencies import get_database_configuration


async def get_session(get_db_config=get_database_configuration):
    """
    Dependency-injected database session.
    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    db_config = await get_db_config()

    # load engine with API timeout setting
    session_factory = await db_config.session_factory()
    async with session_factory() as session:
        async with session.begin():
            yield session
