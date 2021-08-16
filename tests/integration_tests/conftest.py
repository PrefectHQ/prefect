import pytest

from prefect.orion.utilities.database import get_session_factory, get_engine, ENGINES
from prefect.orion.utilities.database import Base

import pytest


@pytest.fixture(scope="function", autouse=True)
async def database_engine():
    """Integration tests run against a shared database with multiple committed
    sessions, so the database needs to be set up and torn down after every test."""

    # clear the engines cache to avoid any state carrying over when the database
    # schema changes on tests witin the same file (avoiding a new import).
    # asyncpg in particular will error otherwise.
    ENGINES.clear()

    # get a new engine
    engine = get_engine()

    try:
        # build the database
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield engine

    finally:
        # tear down the databse
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        # dispose of the engine
        await engine.dispose()


@pytest.fixture
async def database_session(database_engine):
    session_factory = get_session_factory(bind=database_engine)
    async with session_factory() as session:
        yield session
