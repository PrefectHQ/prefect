import datetime

import pendulum
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.orion import models, schemas

from prefect.orion.schemas import states
from prefect.orion.orchestration.rules import (
    FlowOrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.orion.schemas.data import DataDocument
from prefect.orion.database.dependencies import provide_database_interface


@pytest.fixture(scope="session", autouse=True)
async def db_interface():
    return await provide_database_interface()


@pytest.fixture(scope="session", autouse=True)
async def database_engine(db_interface):
    """Produce a database engine"""
    engine = await db_interface.engine()
    try:
        yield engine
    finally:
        await engine.dispose()
        await db_interface.clear_engine_cache()


@pytest.fixture
def print_query(database_engine):
    def inner(query):
        return print(query.compile(database_engine))

    return inner


@pytest.fixture(scope="session", autouse=True)
async def setup_db(database_engine, db_interface):
    """Create all database objects prior to running tests, and drop them when tests are done."""
    try:
        # build the database
        async with database_engine.begin() as conn:
            await conn.run_sync(db_interface.Base.metadata.create_all)
        yield

    finally:
        # tear down the databse
        async with database_engine.begin() as conn:
            await conn.run_sync(db_interface.Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def clear_db(database_engine, db_interface):
    """Clear the database by

    Args:
        database_engine ([type]): [description]
    """
    yield
    async with database_engine.begin() as conn:
        for table in reversed(db_interface.Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def session(db_interface) -> AsyncSession:
    session_factory = await db_interface.session_factory()
    async with session_factory() as session:
        yield session


@pytest.fixture
async def flow(session):
    model = await models.flows.create_flow(
        session=session, flow=schemas.actions.FlowCreate(name="my-flow")
    )
    await session.commit()
    return model


@pytest.fixture
async def flow_run(session, flow):
    model = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version="0.1"),
    )
    await session.commit()
    return model


@pytest.fixture
async def flow_run_state(session, flow_run, db_interface):
    flow_run.set_state(db_interface.FlowRunState(**schemas.states.Pending().dict()))
    await session.commit()
    return flow_run.state


@pytest.fixture
async def task_run(session, flow_run):
    model = await models.task_runs.create_task_run(
        session=session,
        task_run=schemas.actions.TaskRunCreate(
            flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def task_run_state(session, task_run, db_interface):
    task_run.set_state(db_interface.TaskRunState(**schemas.states.Pending().dict()))
    await session.commit()
    return task_run.state


@pytest.fixture
async def flow_run_states(session, flow_run, flow_run_state):
    scheduled_state = schemas.states.State(
        type=schemas.states.StateType.SCHEDULED,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=dict(scheduled_time=pendulum.now("UTC").subtract(seconds=1)),
    )
    scheduled_flow_run_state = (
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=scheduled_state,
            force=True,
        )
    ).state
    running_state = schemas.states.Running()
    running_flow_run_state = (
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run.id,
            state=running_state,
            force=True,
        )
    ).state
    await session.commit()
    return [flow_run_state, scheduled_flow_run_state, running_flow_run_state]


@pytest.fixture
async def task_run_states(session, task_run, task_run_state):
    scheduled_state = schemas.states.State(
        type=schemas.states.StateType.SCHEDULED,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
    )
    scheduled_task_run_state = (
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=scheduled_state,
            force=True,
        )
    ).state
    running_state = schemas.states.Running()
    running_task_run_state = (
        await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run.id,
            state=running_state,
            force=True,
        )
    ).state
    await session.commit()
    return [task_run_state, scheduled_task_run_state, running_task_run_state]


@pytest.fixture
async def deployment(session, flow, flow_function):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment",
            flow_id=flow.id,
            flow_data=DataDocument.encode("cloudpickle", flow_function),
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=1)
            ),
        ),
    )
    await session.commit()
    return deployment


async def commit_task_run_state(
    session, task_run, state_type: states.StateType, state_details=None
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    new_state = schemas.states.State(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
    )

    result = await models.task_runs.set_task_run_state(
        session=session,
        task_run_id=task_run.id,
        state=new_state,
        force=True,
    )

    await session.commit()
    return result.state


async def commit_flow_run_state(
    session, flow_run, state_type: states.StateType, state_details=None
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    new_state = schemas.states.State(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
    )

    result = await models.flow_runs.set_flow_run_state(
        session=session,
        flow_run_id=flow_run.id,
        state=new_state,
        force=True,
    )

    await session.commit()
    return result.state


@pytest.fixture
def initialize_orchestration(
    task_run,
    flow_run,
):
    async def initializer(
        session,
        run_type,
        initial_state_type,
        proposed_state_type,
        initial_details=None,
        proposed_details=None,
    ):

        if run_type == "flow":
            run = flow_run
            context = FlowOrchestrationContext
            state_constructor = commit_flow_run_state
        elif run_type == "task":
            run = task_run
            context = TaskOrchestrationContext
            state_constructor = commit_task_run_state

        initial_state = await state_constructor(
            session,
            run,
            initial_state_type,
            initial_details,
        )

        proposed_details = proposed_details if proposed_details else dict()
        if proposed_state_type is not None:
            psd = states.StateDetails(**proposed_details)
            proposed_state = states.State(type=proposed_state_type, state_details=psd)
        else:
            proposed_state = None

        ctx = context(
            session=session,
            run=run,
            initial_state=initial_state,
            proposed_state=proposed_state,
        )

        return ctx

    return initializer
