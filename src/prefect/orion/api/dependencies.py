from prefect import settings
from prefect.orion.utilities.database import get_session_factory, get_engine


async def get_session():
    """
    Dependency-injected database session.

    The context manager will automatically handle commits,
    rollbacks, and closing the connection.
    """

    # load engine with API timeout setting
    engine = await get_engine(timeout=settings.orion.database.timeout)
    session_factory = await get_session_factory(bind=engine)
    async with session_factory() as session:
        async with session.begin():
            yield session
