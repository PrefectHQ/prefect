import datetime

import pendulum
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.orion import models, schemas
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.orchestration.rules import (
    FlowOrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.orion.schemas import states
from prefect.orion.schemas.data import DataDocument


@pytest.fixture(scope="session", autouse=True)
def db(testing_session_settings):
    return provide_database_interface()


@pytest.fixture(scope="session", autouse=True)
async def database_engine(db):
    """Produce a database engine"""
    engine = await db.engine()
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def print_query(database_engine):
    def inner(query):
        return print(query.compile(database_engine))

    return inner


@pytest.fixture(scope="session", autouse=True)
async def setup_db(database_engine, db):
    """Create all database objects prior to running tests, and drop them when tests are done."""
    try:
        # build the database
        await db.create_db()
        yield

    except Exception as exc:
        # Re-raise with a message containing the url
        raise RuntimeError(
            f"Failed to set up the database at {database_engine.url!r}"
        ) from exc

    finally:
        # tear down the database
        await db.drop_db()


@pytest.fixture(autouse=True)
async def clear_db(database_engine, db):
    """Clear the database by

    Args:
        database_engine ([type]): [description]
    """
    yield
    async with database_engine.begin() as conn:
        for table in reversed(db.Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def session(db) -> AsyncSession:
    session = await db.session()
    async with session:
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
async def flow_run_state(session, flow_run, db):
    flow_run.set_state(db.FlowRunState(**schemas.states.Pending().dict()))
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
async def task_run_state(session, task_run, db):
    task_run.set_state(db.TaskRunState(**schemas.states.Pending().dict()))
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
            flow_runner=schemas.core.FlowRunnerSettings(
                type="subprocess", config={"env": {"TEST_VARIABLE": "1"}}
            ),
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def block_type_x(session):
    block_type = await models.block_types.create_block_type(
        session=session, block_type=schemas.actions.BlockTypeCreate(name="x")
    )
    await session.commit()
    return block_type


@pytest.fixture
async def block_type_y(session):
    block_type = await models.block_types.create_block_type(
        session=session, block_type=schemas.actions.BlockTypeCreate(name="y")
    )
    await session.commit()
    return block_type


@pytest.fixture
async def block_type_z(session):
    block_type = await models.block_types.create_block_type(
        session=session, block_type=schemas.actions.BlockTypeCreate(name="z")
    )
    await session.commit()
    return block_type


@pytest.fixture
async def block_schema(session, block_type_x):
    block_schema = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            type="abc",
            fields={
                "title": "x",
                "type": "object",
                "properties": {"foo": {"title": "Foo", "type": "string"}},
                "required": ["foo"],
            },
            block_type_id=block_type_x.id,
        ),
    )
    await session.commit()
    return block_schema


@pytest.fixture
async def block_document(session, block_schema, block_type_x):
    block_document = await models.block_documents.create_block_document(
        session=session,
        block_document=schemas.actions.BlockDocumentCreate(
            block_schema_id=block_schema.id,
            name="Block 1",
            block_type_id=block_type_x.id,
            data=dict(foo="bar"),
        ),
    )
    await session.commit()
    return block_document


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
def initialize_orchestration(flow):
    async def initializer(
        session,
        run_type,
        initial_state_type,
        proposed_state_type,
        run_override=None,
        run_tags=None,
        initial_details=None,
        proposed_details=None,
    ):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.actions.FlowRunCreate(flow_id=flow.id, flow_version="0.1"),
        )

        if run_type == "flow":
            run = run_override if run_override is not None else flow_run
            if run_tags is not None:
                run.tags = run_tags
            context = FlowOrchestrationContext
            state_constructor = commit_flow_run_state
        elif run_type == "task":
            task_run = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.actions.TaskRunCreate(
                    flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
                ),
            )
            run = run_override if run_override is not None else task_run
            if run_tags is not None:
                run.tags = run_tags
            context = TaskOrchestrationContext
            state_constructor = commit_task_run_state

        await session.commit()

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
