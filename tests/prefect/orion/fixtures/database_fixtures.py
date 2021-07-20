import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from prefect.orion.utilities.database import Base
from prefect.orion.utilities.settings import Settings
from prefect.orion import models
from prefect.orion.api import schemas


@pytest.fixture
async def database_engine():
    """Creates an in memory sqlite database for use in testing"""
    # create an in memory db engine
    engine = create_async_engine("sqlite+aiosqlite://", echo=Settings().database.echo)

    # populate database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine


@pytest.fixture
async def database_session(database_engine):
    try:
        OrionTestAsyncSession = sessionmaker(
            database_engine, future=True, expire_on_commit=False, class_=AsyncSession
        )
        async with OrionTestAsyncSession.begin() as session:
            yield session
    finally:
        # TODO - do we need to clean stuff up here?
        pass


@pytest.fixture
async def flow(database_session):
    return await models.flows.create_flow(
        session=database_session, flow=schemas.Flow(name="my-flow")
    )


@pytest.fixture
async def flow_run(database_session, flow):
    return await models.flow_runs.create_flow_run(
        session=database_session,
        flow_run=schemas.FlowRun(flow_id=flow.id, flow_version="0.1"),
    )
