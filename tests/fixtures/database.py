import asyncio
import datetime
import gc
import uuid
import warnings
from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncGenerator, Callable, Optional, Type

import pendulum
import pytest
from sqlalchemy.exc import InterfaceError
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.blocks.notifications import NotificationBlock
from prefect.filesystems import LocalFileSystem
from prefect.server import models, schemas
from prefect.server.database import orm_models
from prefect.server.database.configurations import ENGINES, TRACKER
from prefect.server.database.dependencies import (
    PrefectDBInterface,
    provide_database_interface,
)
from prefect.server.models.block_registration import run_block_auto_registration
from prefect.server.models.concurrency_limits_v2 import create_concurrency_limit
from prefect.server.orchestration.rules import (
    FlowOrchestrationContext,
    TaskOrchestrationContext,
)
from prefect.server.schemas import states
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.utilities.callables import parameter_schema
from prefect.workers.process import ProcessWorker

AsyncSessionGetter = Callable[[], AsyncContextManager[AsyncSession]]


@pytest.fixture(scope="session", autouse=True)
def db(test_database_connection_url, safety_check_settings):
    return provide_database_interface()


@pytest.fixture(scope="session", autouse=True)
async def database_engine(db: PrefectDBInterface):
    """Produce a database engine"""
    TRACKER.active = True

    engine = await db.engine()

    yield engine

    # At the end of the test session, dispose of _any_ open engines, not just the one
    # that we produced here.  Other engines may have been created from different event
    # loops, and we need to ensure that they are all disposed of.

    engines = list(ENGINES.values())
    ENGINES.clear()

    for engine in engines:
        await engine.dispose()

    # Finally, free up all references to connections and clean up proactively so that
    # we don't have any lingering connections after this.  This should prevent
    # post-test-session ResourceWarning errors about unclosed connections.

    TRACKER.clear()
    gc.collect()


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


@pytest.fixture(autouse=True)
async def clear_db(db, request):
    """
    Delete all data from all tables before running each test, attempting to handle
    connection errors.
    """

    if "clear_db" in request.keywords:
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                async with db.session_context(begin_transaction=True) as session:
                    await session.execute(orm_models.Agent.__table__.delete())
                    await session.execute(orm_models.WorkPool.__table__.delete())

                    for table in reversed(orm_models.Base.metadata.sorted_tables):
                        await session.execute(table.delete())
                    break
            except InterfaceError:
                if attempt < max_retries - 1:
                    print(
                        "Connection issue. Retrying entire deletion operation"
                        f" ({attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    raise

    yield


@pytest.fixture
async def session(db) -> AsyncGenerator[AsyncSession, None]:
    session = await db.session()
    async with session:
        yield session


@pytest.fixture
async def get_server_session(db) -> AsyncSessionGetter:
    """
    Returns a context manager factory that yields
    an database session.

    Note: if you commit or rollback a transaction, scoping
    will be reset. Fixture should be used as a context manager.
    """

    @asynccontextmanager
    async def _get_server_session() -> AsyncGenerator[AsyncSession, None]:
        async with await db.session() as session:
            yield session

    return _get_server_session


@pytest.fixture
async def register_block_types(session):
    await run_block_auto_registration(session=session)
    await session.commit()


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
async def flow_run_with_concurrency_limit(
    session, flow, deployment_with_concurrency_limit
):
    model = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=schemas.actions.FlowRunCreate(
            flow_id=flow.id,
            flow_version="0.1",
            deployment_id=deployment_with_concurrency_limit.id,
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def failed_flow_run_without_deployment(session, flow, deployment):
    flow_run_model = schemas.core.FlowRun(
        state=schemas.states.Failed(),
        flow_id=flow.id,
        flow_version="0.1",
        run_count=1,
    )
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=flow_run_model,
    )
    await models.task_runs.create_task_run(
        session=session,
        task_run=schemas.actions.TaskRunCreate(
            flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
        ),
    )
    await session.commit()
    return flow_run


@pytest.fixture
async def failed_flow_run_with_deployment(session, flow, deployment):
    flow_run_model = schemas.core.FlowRun(
        state=schemas.states.Failed(),
        flow_id=flow.id,
        flow_version="0.1",
        deployment_id=deployment.id,
        run_count=1,
    )
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=flow_run_model,
    )
    await models.task_runs.create_task_run(
        session=session,
        task_run=schemas.actions.TaskRunCreate(
            flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
        ),
    )
    await session.commit()
    return flow_run


@pytest.fixture
async def failed_flow_run_with_deployment_with_no_more_retries(
    session, flow, deployment
):
    flow_run_model = schemas.core.FlowRun(
        state=schemas.states.Failed(),
        flow_id=flow.id,
        flow_version="0.1",
        deployment_id=deployment.id,
        run_count=3,
        empirical_policy={"retries": 2},
    )
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=flow_run_model,
    )
    await models.task_runs.create_task_run(
        session=session,
        task_run=schemas.actions.TaskRunCreate(
            flow_run_id=flow_run.id, task_key="my-key", dynamic_key="0"
        ),
    )
    await session.commit()
    return flow_run


@pytest.fixture
async def nonblockingpaused_flow_run_without_deployment(session, flow, deployment):
    flow_run_model = schemas.core.FlowRun(
        state=schemas.states.Paused(reschedule=True, timeout_seconds=300),
        flow_id=flow.id,
        flow_version="0.1",
        run_count=1,
    )
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=flow_run_model,
    )
    await session.commit()
    return flow_run


@pytest.fixture
async def blocking_paused_flow_run(session, flow, deployment):
    flow_run_model = schemas.core.FlowRun(
        state=schemas.states.Paused(reschedule=False, timeout_seconds=300),
        flow_id=flow.id,
        flow_version="0.1",
        deployment_id=deployment.id,
    )
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=flow_run_model,
    )
    await session.commit()
    return flow_run


@pytest.fixture
async def nonblocking_paused_flow_run(session, flow, deployment):
    flow_run_model = schemas.core.FlowRun(
        state=schemas.states.Paused(reschedule=True, timeout_seconds=300),
        flow_id=flow.id,
        flow_version="0.1",
        deployment_id=deployment.id,
        run_count=1,
    )
    flow_run = await models.flow_runs.create_flow_run(
        session=session,
        flow_run=flow_run_model,
    )
    await session.commit()
    return flow_run


@pytest.fixture
async def flow_run_state(session, flow_run, db):
    flow_run.set_state(db.FlowRunState(**schemas.states.Pending().orm_dict()))
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
    task_run.set_state(db.TaskRunState(**schemas.states.Pending().orm_dict()))
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


# The client-side blocks created below will emit events that may end up interfering with
# other tests by either causing the DB to be locked or by emitting spurious events.
# Thus we're selectively disabling events around those .save calls.


@pytest.fixture
async def storage_document_id(prefect_client, tmpdir):
    return await LocalFileSystem(basepath=str(tmpdir)).save(
        name=f"local-test-{uuid.uuid4()}", client=prefect_client
    )


@pytest.fixture
async def deployment(
    session,
    flow,
    flow_function,
    storage_document_id,
    work_queue_1,  # attached to a work pool called the work_pool fixture named "test-work-pool"
    simple_parameter_schema,
):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"my-deployment-{uuid.uuid4()}",
            tags=["test"],
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1),
                        anchor_date=pendulum.datetime(2020, 1, 1),
                    ),
                    active=True,
                )
            ],
            storage_document_id=storage_document_id,
            path="./subdir",
            entrypoint="/file.py:flow",
            work_queue_name=work_queue_1.name,
            parameter_openapi_schema=simple_parameter_schema.model_dump_for_openapi(),
            work_queue_id=work_queue_1.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def deployment_with_version(
    session,
    flow,
    flow_function,
    storage_document_id,
    work_queue_1,  # attached to a work pool called the work_pool fixture named "test-work-pool"
    simple_parameter_schema,
):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"my-deployment-{uuid.uuid4()}",
            tags=["test"],
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1),
                        anchor_date=pendulum.datetime(2020, 1, 1),
                    ),
                    active=True,
                )
            ],
            storage_document_id=storage_document_id,
            path="./subdir",
            entrypoint="/file.py:flow",
            work_queue_name=work_queue_1.name,
            parameter_openapi_schema=simple_parameter_schema.model_dump_for_openapi(),
            work_queue_id=work_queue_1.id,
            version="1.0",
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def deployment_with_concurrency_limit(
    session,
    flow,
    flow_function,
    storage_document_id,
    work_queue_1,  # attached to a work pool called the work_pool fixture named "test-work-pool"
    simple_parameter_schema,
):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"my-deployment-{uuid.uuid4()}",
            tags=["test"],
            flow_id=flow.id,
            concurrency_limit=42,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1),
                        anchor_date=pendulum.datetime(2020, 1, 1),
                    ),
                    active=True,
                )
            ],
            storage_document_id=storage_document_id,
            path="./subdir",
            entrypoint="/file.py:flow",
            work_queue_name=work_queue_1.name,
            parameter_openapi_schema=simple_parameter_schema.model_dump_for_openapi(),
            work_queue_id=work_queue_1.id,
            version="1.0",
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def deployment_2(
    session,
    flow,
    flow_function,
    storage_document_id,
    work_queue_1,  # attached to a work pool called the work_pool fixture named "test-work-pool"
    simple_parameter_schema,
):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"my-deployment-2-{uuid.uuid4()}",
            tags=["test"],
            flow_id=flow.id,
            schedules=[
                schemas.core.DeploymentSchedule(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1),
                        anchor_date=pendulum.datetime(2020, 1, 1),
                    ),
                    active=True,
                )
            ],
            storage_document_id=storage_document_id,
            path="./subdir",
            entrypoint="/file.py:flow",
            work_queue_name=work_queue_1.name,
            parameter_openapi_schema=simple_parameter_schema.model_dump_for_openapi(),
            work_queue_id=work_queue_1.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def deployment_in_default_work_pool(
    session,
    flow,
    flow_function,
    storage_document_id,
    work_queue,  # not attached to a work pool
    simple_parameter_schema,
):
    """This will create a deployment in the default work pool called `default-agent-pool`"""
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"my-deployment-{uuid.uuid4()}",
            tags=["test"],
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=1),
                anchor_date=pendulum.datetime(2020, 1, 1),
            ),
            storage_document_id=storage_document_id,
            path="./subdir",
            entrypoint="/file.py:flow",
            work_queue_name=work_queue.name,
            parameter_openapi_schema=simple_parameter_schema.model_dump_for_openapi(),
            work_queue_id=work_queue.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
def simple_parameter_schema():
    def hello(name=None):
        pass

    return parameter_schema(hello)


@pytest.fixture
async def deployment_in_non_default_work_pool(
    session,
    flow,
    flow_function,
    storage_document_id,
    work_queue_1,
    simple_parameter_schema,
):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"my-deployment-{uuid.uuid4()}",
            tags=["test"],
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=datetime.timedelta(days=1),
                anchor_date=pendulum.datetime(2020, 1, 1),
            ),
            storage_document_id=storage_document_id,
            path="./subdir",
            entrypoint="/file.py:flow",
            work_queue_name="wq",
            parameter_openapi_schema=simple_parameter_schema.model_dump_for_openapi(),
            work_queue_id=work_queue_1.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def deployment_with_parameter_schema(
    session,
    flow,
):
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name=f"my-deployment-with-parameter-schema{uuid.uuid4()}",
            flow_id=flow.id,
            parameter_openapi_schema={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
            parameters={"x": "y"},
            enforce_parameter_schema=True,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.actions.WorkQueueCreate(
            name=f"wq-1-{uuid.uuid4()}",
            description="All about my work queue",
            priority=1,
        ),
    )
    await session.commit()
    return work_queue


@pytest.fixture
async def work_pool(session):
    model = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name=f"test-work-pool-{uuid.uuid4()}",
            type="test-type",
            base_job_template={
                "job_configuration": {
                    "command": "{{ command }}",
                },
                "variables": {
                    "properties": {
                        "command": {
                            "type": "string",
                            "title": "Command",
                        },
                    },
                    "required": [],
                },
            },
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def work_pool_with_image_variable(session):
    model = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="test-work-pool",
            type="test-type",
            base_job_template={
                "job_configuration": {
                    "command": "{{ command }}",
                    "image": "{{ image }}",
                    "image_pull_policy": "{{ image_pull_policy }}",
                },
                "variables": {
                    "properties": {
                        "command": {
                            "type": "string",
                            "title": "Command",
                        },
                        "image": {
                            "type": "string",
                            "title": "Image",
                        },
                        "image_pull_policy": {
                            "enum": ["IfNotPresent", "Always", "Never"],
                            "type": "string",
                            "title": "Image Pull Policy",
                            "default": "IfNotPresent",
                        },
                    },
                    "required": [],
                },
            },
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def process_work_pool(session):
    model = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="process-work-pool",
            type=ProcessWorker.type,
            base_job_template=ProcessWorker.get_default_base_job_template(),
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def push_work_pool(session):
    model = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="push-work-pool",
            type="push-work-pool:push",
            base_job_template={
                "job_configuration": {
                    "command": "{{ command }}",
                    "image": "{{ image }}",
                },
                "variables": {
                    "properties": {
                        "command": {
                            "type": "string",
                            "title": "Command",
                        },
                        "image": {
                            "type": "string",
                            "title": "Image",
                        },
                    },
                    "required": [],
                },
            },
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def managed_work_pool(session):
    model = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="mex-work-pool",
            type="mex-work-pool:managed",
            base_job_template={
                "job_configuration": {
                    "command": "{{ command }}",
                    "image": "{{ image }}",
                },
                "variables": {
                    "properties": {
                        "command": {
                            "type": "string",
                            "title": "Command",
                        },
                        "image": {
                            "type": "string",
                            "title": "Image",
                        },
                    },
                    "required": [],
                },
            },
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def prefect_agent_work_pool(session):
    model = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name="process-work-pool",
            type="prefect-agent",
        ),
    )
    await session.commit()
    return model


@pytest.fixture
async def work_queue_1(session, work_pool):
    model = await models.workers.create_work_queue(
        session=session,
        work_pool_id=work_pool.id,
        work_queue=schemas.actions.WorkQueueCreate(name=f"wq-1-{uuid.uuid4()}"),
    )
    await session.commit()
    return model


@pytest.fixture
async def work_queue_2(session, work_pool):
    model = await models.workers.create_work_queue(
        session=session,
        work_pool_id=work_pool.id,
        work_queue=schemas.actions.WorkQueueCreate(name="wq-2"),
    )
    await session.commit()
    return model


@pytest.fixture
async def block_type_x(session):
    block_type = await models.block_types.create_block_type(
        session=session,
        block_type=schemas.actions.BlockTypeCreate(name="x", slug="x-fixture"),
    )
    await session.commit()
    return block_type


@pytest.fixture
async def block_type_y(session):
    block_type = await models.block_types.create_block_type(
        session=session, block_type=schemas.actions.BlockTypeCreate(name="y", slug="y")
    )
    await session.commit()
    return block_type


@pytest.fixture
async def block_type_z(session):
    block_type = await models.block_types.create_block_type(
        session=session, block_type=schemas.actions.BlockTypeCreate(name="z", slug="z")
    )
    await session.commit()
    return block_type


@pytest.fixture
async def block_schema(session, block_type_x):
    fields = {
        "title": "x",
        "type": "object",
        "properties": {"foo": {"title": "Foo", "type": "string"}},
        "required": ["foo"],
        "block_schema_references": {},
        "block_type_slug": block_type_x.slug,
    }
    block_schema = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields=fields,
            block_type_id=block_type_x.id,
        ),
    )
    await session.commit()
    return block_schema


@pytest.fixture
async def nested_block_schema(session, block_type_y, block_type_x, block_schema):
    block_schema = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={
                "title": "y",
                "type": "object",
                "properties": {"bar": {"$ref": "#/definitions/x"}},
                "required": ["bar"],
                "block_schema_references": {
                    "bar": {
                        "block_schema_checksum": block_schema.checksum,
                        "block_type_slug": block_type_x.slug,
                    }
                },
                "block_type_slug": block_type_y.slug,
                "definitions": {
                    "x": {
                        "title": "x",
                        "type": "object",
                        "properties": {"foo": {"title": "Foo", "type": "string"}},
                        "required": ["foo"],
                        "block_schema_references": {},
                        "block_type_slug": block_type_x.slug,
                    }
                },
            },
            block_type_id=block_type_y.id,
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
            name="block-1",
            block_type_id=block_type_x.id,
            data=dict(foo="bar"),
        ),
    )
    await session.commit()
    return block_document


async def commit_task_run_state(
    session,
    task_run,
    state_type: states.StateType,
    state_details=None,
    state_data=None,
    state_name=None,
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    new_state = schemas.states.State(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
        data=state_data,
        name=state_name,
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
    session,
    flow_run,
    state_type: states.StateType,
    state_details=None,
    state_data=None,
    state_name=None,
):
    if state_type is None:
        return None
    state_details = dict() if state_details is None else state_details

    new_state = schemas.states.State(
        type=state_type,
        timestamp=pendulum.now("UTC").subtract(seconds=5),
        state_details=state_details,
        data=state_data,
        name=state_name,
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
        initial_flow_run_state_type=None,
        run_override=None,
        run_tags=None,
        initial_details=None,
        initial_state_data=None,
        proposed_details=None,
        flow_retries: Optional[int] = None,
        flow_run_count: Optional[int] = None,
        resuming: Optional[bool] = None,
        initial_flow_run_state_details=None,
        initial_state_name: Optional[str] = None,
        proposed_state_name: Optional[str] = None,
        deployment_id: Optional[str] = None,
    ):
        flow_create_kwargs = {}
        empirical_policy = {}
        if initial_flow_run_state_details is None:
            initial_flow_run_state_details = {}
        if flow_retries:
            empirical_policy.update({"retries": flow_retries})
        if resuming:
            empirical_policy.update({"resuming": resuming})

        flow_create_kwargs.update(
            {"empirical_policy": schemas.core.FlowRunPolicy(**empirical_policy)}
        )

        if flow_run_count:
            flow_create_kwargs.update({"run_count": flow_run_count})

        if deployment_id:
            flow_create_kwargs.update({"deployment_id": deployment_id})

        flow_run_model = schemas.core.FlowRun(
            flow_id=flow.id, flow_version="0.1", **flow_create_kwargs
        )

        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=flow_run_model,
        )

        if run_type == "flow":
            run = run_override if run_override is not None else flow_run
            if run_tags is not None:
                run.tags = run_tags
            context = FlowOrchestrationContext
            state_constructor = commit_flow_run_state
        elif run_type == "task":
            if initial_flow_run_state_type:
                flow_state_constructor = commit_flow_run_state
                kwargs = {}
                if initial_flow_run_state_details:
                    kwargs["state_details"] = initial_flow_run_state_details
                await flow_state_constructor(
                    session, flow_run, initial_flow_run_state_type, **kwargs
                )
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
        else:
            raise NotImplementedError("Only 'task' and 'flow' run types are supported")

        await session.commit()

        initial_state = await state_constructor(
            session,
            run,
            initial_state_type,
            initial_details,
            state_data=initial_state_data,
            state_name=initial_state_name,
        )

        proposed_details = proposed_details if proposed_details else dict()
        if proposed_state_type is not None:
            psd = states.StateDetails(**proposed_details)
            proposed_state = states.State(
                type=proposed_state_type, state_details=psd, name=proposed_state_name
            )
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


@pytest.fixture
def DebugPrintNotification() -> Type[NotificationBlock]:
    class DebugPrintNotification(NotificationBlock):
        """
        Notification block that prints a message, useful for debugging.
        """

        _block_type_name = "Debug Print Notification"
        # singleton block name
        _block_document_name = "Debug Print Notification"

        async def notify(self, subject: str, body: str):
            print(body)

    return DebugPrintNotification


@pytest.fixture
async def notifier_block(
    DebugPrintNotification: Type[NotificationBlock], in_memory_prefect_client
):
    # Ignore warnings from block reuse in fixture
    warnings.filterwarnings("ignore", category=UserWarning)

    block = DebugPrintNotification()
    await block.save("debug-print-notification", client=in_memory_prefect_client)
    return block


@pytest.fixture
async def worker_deployment_wq1(
    session,
    flow,
    flow_function,
    work_queue_1,
):
    def hello(name: str = "world"):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment 1",
            tags=["test"],
            flow_id=flow.id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1),
                        anchor_date=pendulum.datetime(2020, 1, 1),
                    )
                )
            ],
            path="./subdir",
            entrypoint="/file.py:flow",
            parameter_openapi_schema=parameter_schema(hello).model_dump_for_openapi(),
            work_queue_id=work_queue_1.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def worker_deployment_infra_wq1(session, flow, flow_function, work_queue_1):
    def hello(name: str = "world"):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment 2",
            tags=["test"],
            flow_id=flow.id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1),
                        anchor_date=pendulum.datetime(2020, 1, 1),
                    )
                )
            ],
            path="./subdir",
            entrypoint="/file.py:flow",
            parameter_openapi_schema=parameter_schema(hello).model_dump_for_openapi(),
            work_queue_id=work_queue_1.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def worker_deployment_wq_2(
    session,
    flow,
    flow_function,
    work_queue_2,
):
    def hello(name: str = "world"):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment 2",
            tags=["test"],
            flow_id=flow.id,
            schedules=[
                schemas.actions.DeploymentScheduleCreate(
                    schedule=schemas.schedules.IntervalSchedule(
                        interval=datetime.timedelta(days=1),
                        anchor_date=pendulum.datetime(2020, 1, 1),
                    )
                )
            ],
            path="./subdir",
            entrypoint="/file.py:flow",
            parameter_openapi_schema=parameter_schema(hello).model_dump_for_openapi(),
            work_queue_id=work_queue_2.id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def concurrency_limit_v2(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="my-limit",
            limit=42,
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)
