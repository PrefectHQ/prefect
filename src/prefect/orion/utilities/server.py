from prefect.orion.utilities.database import OrionAsyncSession


async def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    async with OrionAsyncSession.begin() as session:
        yield session
