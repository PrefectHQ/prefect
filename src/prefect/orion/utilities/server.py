from fastapi import Request
from prefect.orion.utilities.database import async_session


async def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    async with async_session.begin() as session:
        yield session
