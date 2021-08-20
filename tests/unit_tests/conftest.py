import pendulum
import pytest

from prefect import settings
from prefect.orion import models, schemas
from prefect.orion.api.dependencies import get_session
from prefect.orion.api.server import app
from prefect.orion.utilities.database import Base, get_session_factory, get_engine
from fastapi.testclient import TestClient


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
async def session(database_engine):
    """Test database session. All unit tests share this session. At the end of
    each test, the session is rolled back to restore the original database
    condition and avoid carrying over state.
    """
    session_factory = get_session_factory(bind=database_engine)
    async with session_factory() as session:

        async def get_nested_shared_session():
            """Create a nested session that can safely be rolled back inside a
            unit test
            """
            nested = await session.begin_nested()
            try:
                yield session
            except Exception as exc:
                await nested.rollback()
                raise exc

        app.dependency_overrides[get_session] = get_nested_shared_session

        try:
            yield session
        finally:
            # reset the dependencies
            app.dependency_overrides = {}
            # rollback all changes
            await session.rollback()


@pytest.fixture(autouse=True)
def mock_asgi_client(monkeypatch, database_engine):
    """
    The ASGIClient runs in a different event loop, which means it can't easily
    access the shared database session when running against postgresql (sqlite
    works fine), because the postgresql connections can't be shared across
    loops. To work around this, we replace it with the fastapi TestClient for
    postgres unit tests only. The TestClient is a (much slower) implementation
    of the ASGIClient that exposes ASGI applications but doesn't require a
    separate event loop.
    """
    if database_engine.dialect.name == "postgresql":
        monkeypatch.setattr(
            "prefect.client._ASGIClient", lambda app, **kw: TestClient(app)
        )


@pytest.fixture
async def flow(session):
    model = await models.flows.create_flow(
        session=session, flow=schemas.actions.FlowCreate(name="my-flow")
    )
    return model


@pytest.fixture
async def flow_run(session, flow):
    model = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version="0.1"),
    )
    return model


@pytest.fixture
async def task_run(session, flow_run):
    fake_task_run = schemas.actions.TaskRunCreate(
        flow_run_id=flow_run.id, task_key="my-key"
    )
    model = await models.task_runs.create_task_run(
        session=session,
        task_run=fake_task_run,
    )
    await session.flush()
    return model


@pytest.fixture
async def flow_run_states(session, flow_run):
    scheduled_state = schemas.actions.StateCreate(
        type=schemas.states.StateType.SCHEDULED,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=dict(scheduled_time=pendulum.now("UTC").subtract(seconds=1)),
    )
    scheduled_flow_run_state = await models.flow_run_states.create_flow_run_state(
        session=session,
        flow_run_id=flow_run.id,
        state=scheduled_state,
    )
    running_state = schemas.actions.StateCreate(type="RUNNING")
    running_flow_run_state = await models.flow_run_states.create_flow_run_state(
        session=session,
        flow_run_id=flow_run.id,
        state=running_state,
    )
    return [scheduled_flow_run_state, running_flow_run_state]


@pytest.fixture
async def task_run_states(session, task_run):
    scheduled_state = schemas.actions.StateCreate(
        type=schemas.states.StateType.SCHEDULED,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
    )
    scheduled_task_run_state = await models.task_run_states.create_task_run_state(
        session=session,
        task_run_id=task_run.id,
        state=scheduled_state,
    )
    running_state = schemas.actions.StateCreate(type="RUNNING")
    running_task_run_state = await models.task_run_states.create_task_run_state(
        session=session,
        task_run_id=task_run.id,
        state=running_state,
    )
    return [scheduled_task_run_state, running_task_run_state]
