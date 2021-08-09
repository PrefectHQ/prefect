from prefect.orion.utilities.database import Base, get_engine
from prefect.orion.utilities.database import get_session_factory
import pendulum
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from prefect import settings
from prefect.orion import models, schemas
from prefect.orion.api.server import app
from prefect.orion.api.dependencies import get_session


@pytest.fixture(scope="package", autouse=True)
async def setup_db(database_engine):
    """Unit tests run against a shared, rolled-back database session,
    so the database only needs to be set up and torn down once, at the start
    and end of all tests."""
    try:
        # reset database before integration tests run
        async with database_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield

    finally:
        # clear database tables
        async with database_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def database_session(database_engine):
    """Test database session. All unit tests share this session. At the end of
    each test, the session is rolled back to restore the original database
    condition and avoid carrying over state.
    """
    OrionSession = get_session_factory(database_engine)

    async with OrionSession() as session:

        app.dependency_overrides[get_session] = lambda: session

        try:
            yield session
        finally:
            app.dependency_overrides = {}
            await session.rollback()


@pytest.fixture
async def flow(database_session):
    model = await models.flows.create_flow(
        session=database_session, flow=schemas.actions.FlowCreate(name="my-flow")
    )
    return model


@pytest.fixture
async def flow_run(database_session, flow):
    model = await models.flow_runs.create_flow_run(
        session=database_session,
        flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version="0.1"),
    )
    return model


@pytest.fixture
async def task_run(database_session, flow_run):
    fake_task_run = schemas.actions.TaskRunCreate(
        flow_run_id=flow_run.id, task_key="my-key"
    )
    model = await models.task_runs.create_task_run(
        session=database_session,
        task_run=fake_task_run,
    )
    return model


@pytest.fixture
async def flow_run_states(database_session, flow_run):
    scheduled_state = schemas.actions.StateCreate(
        type=schemas.states.StateType.SCHEDULED,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
    )
    scheduled_flow_run_state = await models.flow_run_states.create_flow_run_state(
        session=database_session,
        flow_run_id=flow_run.id,
        state=scheduled_state,
    )
    running_state = schemas.actions.StateCreate(type="RUNNING")
    running_flow_run_state = await models.flow_run_states.create_flow_run_state(
        session=database_session,
        flow_run_id=flow_run.id,
        state=running_state,
    )
    return [scheduled_flow_run_state, running_flow_run_state]


@pytest.fixture
async def task_run_states(database_session, task_run):
    scheduled_state = schemas.actions.StateCreate(
        type=schemas.states.StateType.SCHEDULED,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
    )
    scheduled_task_run_state = await models.task_run_states.create_task_run_state(
        session=database_session,
        task_run_id=task_run.id,
        state=scheduled_state,
    )
    running_state = schemas.actions.StateCreate(type="RUNNING")
    running_task_run_state = await models.task_run_states.create_task_run_state(
        session=database_session,
        task_run_id=task_run.id,
        state=running_state,
    )
    return [scheduled_task_run_state, running_task_run_state]
