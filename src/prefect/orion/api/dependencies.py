from prefect.orion.utilities.database import get_session_factory


async def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """
    session_factory = await get_session_factory()
    async with session_factory() as session:
        async with session.begin():
            yield session
