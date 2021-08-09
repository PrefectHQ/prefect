import pytest

from prefect.orion.utilities.database import get_session_factory
from prefect.orion.utilities.database import Base

import pytest


@pytest.fixture(scope="function", autouse=True)
async def setup_db(database_engine):
    """Integration tests run against a shared database with multiple committed
    sessions, so the database needs to be set up and torn down after every test."""
    try:
        # reset database before integration tests run
        async with database_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield

    finally:
        # clear database tables
        async with database_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def database_session(database_engine):
    OrionSession = get_session_factory(database_engine)
    yield OrionSession()
