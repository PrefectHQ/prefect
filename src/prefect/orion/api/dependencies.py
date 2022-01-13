"""
Utilities for injecting FastAPI dependencies.
"""
from fastapi import Depends

from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.server import response_scoped_dependency


@response_scoped_dependency
async def get_session(db: OrionDBInterface = Depends(provide_database_interface)):
    """
    Dependency-injected database session.

    The context manager will automatically handle commits, rollbacks, and closing the
    connection.

    A `response_scoped_dependency` is used to ensure this session is closed before the
    response is returned to a client.
    """
    session = await db.session()
    async with session:
        async with session.begin():
            yield session
