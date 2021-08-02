import pendulum
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from prefect.orion.utilities.database import Base, get_engine, get_session_factory
from prefect import settings
from prefect.orion import models, schemas
import logging
import asyncio
import inspect

import pytest


@pytest.fixture(scope="session")
async def database_engine():
    """Creates an in memory sqlite database for use in testing. For performance,
    the database is created only once, at the beginning of testing. Subsequent
    sessions roll themselves back at the end of each test to restore the
    database.
    """

    engine = get_engine()

    # populate database tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def database_session(database_engine):
    OrionSession = get_session_factory(database_engine)
    yield OrionSession()
