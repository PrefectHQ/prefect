"""
Utilities for injecting FastAPI dependencies.
"""

from prefect import settings
from prefect.orion.database.dependencies import provide_database_interface


async def get_session(db=None):
    """
    Dependency-injected database session.
    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    # we cant directly inject into FastAPI dependencies because
    # they are converted to async_generator objects
    db = db or await provide_database_interface()

    # load engine with API timeout setting
    session_factory = await db.session_factory()
    async with session_factory() as session:
        async with session.begin():
            yield session
