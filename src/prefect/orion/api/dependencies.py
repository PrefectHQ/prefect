"""
Utilities for injecting FastAPI dependencies.
"""

from prefect import settings
from prefect.orion.database.dependencies import get_database_configuration


async def get_session(db_config=None):
    """
    Dependency-injected database session.
    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    # we cant directly inject into FastAPI dependencies because
    # they are converted to async_generator objects
    db_config = db_config or await get_database_configuration()

    # load engine with API timeout setting
    session_factory = await db_config.session_factory()
    async with session_factory() as session:
        async with session.begin():
            yield session
