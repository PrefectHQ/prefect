import pytest

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from prefect.orion.utilities.database import reset_db


@pytest.fixture(autouse=True, scope="function")
async def database_engine():
    """Creates an in memory sqlite database for use in testing"""
    try:
        # create an in memory db engine
        engine = create_async_engine("sqlite+aiosqlite://", echo=True)
        # populate database tables
        await reset_db(engine=engine)
        yield engine
    finally:
        # TODO - do we need to delete anything or clean stuff up?
        pass


@pytest.fixture(autouse=True, scope="function")
async def database_session(database_engine):
    try:
        async_session = sessionmaker(
            database_engine, future=True, expire_on_commit=False, class_=AsyncSession
        )
        async with async_session.begin() as session:
            yield session
    finally:
        # TODO - do we need to clean stuff up here?
        pass
