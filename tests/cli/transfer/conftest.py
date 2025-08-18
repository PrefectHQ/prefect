"""
Fixtures for CLI transfer tests.

These fixtures create isolated resources for migration testing,
avoiding interference with other tests.
"""

import datetime
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.client.schemas.objects import Variable, WorkPool, WorkQueue
from prefect.client.schemas.responses import DeploymentResponse
from prefect.filesystems import LocalFileSystem
from prefect.server import models, schemas
from prefect.utilities.callables import parameter_schema
from prefect.workers.process import ProcessWorker


# Flow fixtures
@pytest.fixture
async def transfer_flow(session: AsyncSession):
    """Create a flow for transfer testing."""
    from prefect.client.schemas.objects import Flow

    model = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name=f"transfer-flow-{uuid.uuid4()}")
    )
    await session.commit()

    # Convert to client schema object
    return Flow(
        id=model.id,
        name=model.name,
        tags=model.tags,
        labels=model.labels,
        created=model.created,
        updated=model.updated,
    )


@pytest.fixture
async def transfer_flow_2(session: AsyncSession):
    """Create a second flow for transfer testing."""
    model = await models.flows.create_flow(
        session=session, flow=schemas.core.Flow(name=f"transfer-flow-2-{uuid.uuid4()}")
    )
    await session.commit()
    return model


# Work Pool fixtures
@pytest.fixture
async def transfer_work_pool(session: AsyncSession):
    """Create a regular work pool for transfer testing."""
    from prefect.client.schemas.objects import WorkPoolStorageConfiguration

    orm_work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name=f"transfer-work-pool-{uuid.uuid4()}",
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

    # Convert to client object
    return WorkPool(
        id=orm_work_pool.id,
        name=orm_work_pool.name,
        description=orm_work_pool.description,
        type=orm_work_pool.type,
        base_job_template=orm_work_pool.base_job_template,
        is_paused=orm_work_pool.is_paused,
        concurrency_limit=orm_work_pool.concurrency_limit,
        status=getattr(orm_work_pool, "status", None),
        storage_configuration=WorkPoolStorageConfiguration(),
        default_queue_id=orm_work_pool.default_queue_id,
        created=orm_work_pool.created,
        updated=orm_work_pool.updated,
    )


@pytest.fixture
async def transfer_push_work_pool(session: AsyncSession):
    """Create a push work pool for transfer testing."""
    from prefect.client.schemas.objects import WorkPoolStorageConfiguration

    orm_work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name=f"transfer-push-pool-{uuid.uuid4()}",
            type="push-work-pool:push",
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

    # Convert to client object
    return WorkPool(
        id=orm_work_pool.id,
        name=orm_work_pool.name,
        description=orm_work_pool.description,
        type=orm_work_pool.type,
        base_job_template=orm_work_pool.base_job_template,
        is_paused=orm_work_pool.is_paused,
        concurrency_limit=orm_work_pool.concurrency_limit,
        status=getattr(orm_work_pool, "status", None),
        storage_configuration=WorkPoolStorageConfiguration(),
        default_queue_id=orm_work_pool.default_queue_id,
        created=orm_work_pool.created,
        updated=orm_work_pool.updated,
    )


@pytest.fixture
async def transfer_managed_work_pool(session: AsyncSession):
    """Create a managed work pool for transfer testing."""
    from prefect.client.schemas.objects import WorkPoolStorageConfiguration

    orm_work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name=f"transfer-managed-pool-{uuid.uuid4()}",
            type="mex-work-pool:managed",
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

    # Convert to client object
    return WorkPool(
        id=orm_work_pool.id,
        name=orm_work_pool.name,
        description=orm_work_pool.description,
        type=orm_work_pool.type,
        base_job_template=orm_work_pool.base_job_template,
        is_paused=orm_work_pool.is_paused,
        concurrency_limit=orm_work_pool.concurrency_limit,
        status=getattr(orm_work_pool, "status", None),
        storage_configuration=WorkPoolStorageConfiguration(),
        default_queue_id=orm_work_pool.default_queue_id,
        created=orm_work_pool.created,
        updated=orm_work_pool.updated,
    )


@pytest.fixture
async def transfer_process_work_pool(session: AsyncSession):
    """Create a process work pool for transfer testing."""
    from prefect.client.schemas.objects import WorkPoolStorageConfiguration

    orm_work_pool = await models.workers.create_work_pool(
        session=session,
        work_pool=schemas.actions.WorkPoolCreate(
            name=f"transfer-process-pool-{uuid.uuid4()}",
            type=ProcessWorker.type,
            base_job_template=ProcessWorker.get_default_base_job_template(),
        ),
    )
    await session.commit()

    # Convert to client object
    return WorkPool(
        id=orm_work_pool.id,
        name=orm_work_pool.name,
        description=orm_work_pool.description,
        type=orm_work_pool.type,
        base_job_template=orm_work_pool.base_job_template,
        is_paused=orm_work_pool.is_paused,
        concurrency_limit=orm_work_pool.concurrency_limit,
        status=getattr(orm_work_pool, "status", None),
        storage_configuration=WorkPoolStorageConfiguration(),
        default_queue_id=orm_work_pool.default_queue_id,
        created=orm_work_pool.created,
        updated=orm_work_pool.updated,
    )


# Work Queue fixtures
@pytest.fixture
async def transfer_work_queue(session: AsyncSession):
    """Create a standalone work queue for transfer testing."""
    orm_work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.actions.WorkQueueCreate(
            name=f"transfer-wq-{uuid.uuid4()}",
            description="Transfer test work queue",
            priority=1,
            concurrency_limit=None,
            filter=None,
        ),
    )
    await session.commit()

    # Convert to client object
    return WorkQueue(
        id=orm_work_queue.id,
        name=orm_work_queue.name,
        description=orm_work_queue.description,
        priority=orm_work_queue.priority,
        concurrency_limit=orm_work_queue.concurrency_limit,
        filter=orm_work_queue.filter,
        is_paused=orm_work_queue.is_paused,
        last_polled=orm_work_queue.last_polled,
        status=getattr(orm_work_queue, "status", None),
        work_pool_id=None,
        created=orm_work_queue.created,
        updated=orm_work_queue.updated,
    )


@pytest.fixture
async def transfer_work_queue_with_pool(session: AsyncSession, transfer_work_pool):
    """Create a work queue associated with a work pool for transfer testing."""
    orm_work_queue = await models.workers.create_work_queue(
        session=session,
        work_pool_id=transfer_work_pool.id,
        work_queue=schemas.actions.WorkQueueCreate(
            name=f"transfer-wq-with-pool-{uuid.uuid4()}",
            priority=1,
            concurrency_limit=None,
            filter=None,
        ),
    )
    await session.commit()

    # Convert to client object
    return WorkQueue(
        id=orm_work_queue.id,
        name=orm_work_queue.name,
        description=orm_work_queue.description,
        priority=orm_work_queue.priority,
        concurrency_limit=orm_work_queue.concurrency_limit,
        filter=orm_work_queue.filter,
        is_paused=orm_work_queue.is_paused,
        last_polled=orm_work_queue.last_polled,
        status=getattr(orm_work_queue, "status", None),
        work_pool_id=transfer_work_pool.id,
        work_pool_name=transfer_work_pool.name,
        created=orm_work_queue.created,
        updated=orm_work_queue.updated,
    )


# Block fixtures
@pytest.fixture
async def transfer_block_type_x(session: AsyncSession):
    """Create a block type X for transfer testing."""
    from prefect.client.schemas.objects import BlockType

    orm_block_type = await models.block_types.create_block_type(
        session=session,
        block_type=schemas.actions.BlockTypeCreate(
            name=f"transfer-x-{uuid.uuid4()}", slug=f"transfer-x-{uuid.uuid4()}"
        ),
    )
    await session.commit()

    # Convert to client schema object
    return BlockType(
        id=orm_block_type.id,
        name=orm_block_type.name,
        slug=orm_block_type.slug,
        logo_url=orm_block_type.logo_url,
        documentation_url=orm_block_type.documentation_url,
        description=orm_block_type.description,
        code_example=orm_block_type.code_example,
        is_protected=orm_block_type.is_protected,
        created=orm_block_type.created,
        updated=orm_block_type.updated,
    )


@pytest.fixture
async def transfer_block_type_y(session: AsyncSession):
    """Create a block type Y for transfer testing."""
    from prefect.client.schemas.objects import BlockType

    orm_block_type = await models.block_types.create_block_type(
        session=session,
        block_type=schemas.actions.BlockTypeCreate(
            name=f"transfer-y-{uuid.uuid4()}", slug=f"transfer-y-{uuid.uuid4()}"
        ),
    )
    await session.commit()

    # Convert to client schema object
    return BlockType(
        id=orm_block_type.id,
        name=orm_block_type.name,
        slug=orm_block_type.slug,
        logo_url=orm_block_type.logo_url,
        documentation_url=orm_block_type.documentation_url,
        description=orm_block_type.description,
        code_example=orm_block_type.code_example,
        is_protected=orm_block_type.is_protected,
        created=orm_block_type.created,
        updated=orm_block_type.updated,
    )


@pytest.fixture
async def transfer_block_schema(session: AsyncSession, transfer_block_type_x):
    """Create a block schema for transfer testing."""
    from prefect.client.schemas.objects import BlockSchema

    fields = {
        "title": "transfer-x",
        "type": "object",
        "properties": {"foo": {"title": "Foo", "type": "string"}},
        "required": ["foo"],
        "block_schema_references": {},
        "block_type_slug": transfer_block_type_x.slug,
    }
    orm_block_schema = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields=fields,
            block_type_id=transfer_block_type_x.id,
        ),
    )
    await session.commit()

    # Convert to client schema object
    return BlockSchema(
        id=orm_block_schema.id,
        checksum=orm_block_schema.checksum,
        fields=orm_block_schema.fields,
        block_type_id=orm_block_schema.block_type_id,
        block_type=transfer_block_type_x,
        capabilities=orm_block_schema.capabilities,
        version=orm_block_schema.version,
        created=orm_block_schema.created,
        updated=orm_block_schema.updated,
    )


@pytest.fixture
async def transfer_nested_block_schema(
    session: AsyncSession,
    transfer_block_type_y,
    transfer_block_type_x,
    transfer_block_schema,
):
    """Create a nested block schema with references for transfer testing."""
    block_schema = await models.block_schemas.create_block_schema(
        session=session,
        block_schema=schemas.actions.BlockSchemaCreate(
            fields={
                "title": "transfer-y",
                "type": "object",
                "properties": {"bar": {"$ref": "#/definitions/transfer-x"}},
                "required": ["bar"],
                "block_schema_references": {
                    "bar": {
                        "block_schema_checksum": transfer_block_schema.checksum,
                        "block_type_slug": transfer_block_type_x.slug,
                    }
                },
                "block_type_slug": transfer_block_type_y.slug,
                "definitions": {
                    "transfer-x": {
                        "title": "transfer-x",
                        "type": "object",
                        "properties": {"foo": {"title": "Foo", "type": "string"}},
                        "required": ["foo"],
                        "block_schema_references": {},
                        "block_type_slug": transfer_block_type_x.slug,
                    }
                },
            },
            block_type_id=transfer_block_type_y.id,
        ),
    )
    await session.commit()
    return block_schema


@pytest.fixture
async def transfer_block_document(
    session: AsyncSession, transfer_block_schema, transfer_block_type_x
):
    """Create a block document for transfer testing."""
    from prefect.client.schemas.objects import BlockDocument

    orm_block_document = await models.block_documents.create_block_document(
        session=session,
        block_document=schemas.actions.BlockDocumentCreate(
            block_schema_id=transfer_block_schema.id,
            name=f"transfer-block-{uuid.uuid4()}",
            block_type_id=transfer_block_type_x.id,
            data=dict(foo="transfer-bar"),
        ),
    )
    await session.commit()

    # Convert to client schema object
    return BlockDocument(
        id=orm_block_document.id,
        name=orm_block_document.name,
        data=orm_block_document.data,
        block_schema_id=orm_block_document.block_schema_id,
        block_schema=transfer_block_schema,
        block_type_id=orm_block_document.block_type_id,
        block_type=transfer_block_type_x,
        block_document_references=orm_block_document.block_document_references or {},
        is_anonymous=orm_block_document.is_anonymous,
        created=orm_block_document.created,
        updated=orm_block_document.updated,
    )


@pytest.fixture
async def transfer_block_document_with_references(
    session: AsyncSession,
    transfer_nested_block_schema,
    transfer_block_type_y,
    transfer_block_document,
):
    """Create a block document with references to other block documents."""
    block_document = await models.block_documents.create_block_document(
        session=session,
        block_document=schemas.actions.BlockDocumentCreate(
            block_schema_id=transfer_nested_block_schema.id,
            name=f"transfer-nested-block-{uuid.uuid4()}",
            block_type_id=transfer_block_type_y.id,
            data=dict(bar=dict(foo="nested-transfer-bar")),
            block_document_references={
                "bar": {
                    "block_document_id": str(transfer_block_document.id),
                }
            },
        ),
    )
    await session.commit()
    return block_document


# Storage fixtures
@pytest.fixture
async def transfer_storage_document_id(prefect_client, tmp_path):
    """Create a storage document for transfer testing."""
    return await LocalFileSystem(basepath=str(tmp_path)).save(
        name=f"transfer-local-{uuid.uuid4()}", client=prefect_client
    )


# Deployment fixtures
def transfer_parameter_schema():
    """Simple parameter schema for transfer testing."""

    def hello(name=None):
        pass

    return parameter_schema(hello)


@pytest.fixture
async def transfer_deployment(transfer_flow):
    """Create a deployment for transfer testing."""
    from prefect.client.schemas.objects import DeploymentSchedule
    from prefect.client.schemas.schedules import IntervalSchedule

    # Create a simple DeploymentResponse object directly
    return DeploymentResponse(
        id=uuid.uuid4(),
        name=f"transfer-deployment-{uuid.uuid4()}",
        flow_id=transfer_flow.id,
        schedules=[
            DeploymentSchedule(
                id=uuid.uuid4(),
                deployment_id=uuid.uuid4(),  # Will be overridden
                schedule=IntervalSchedule(
                    interval=datetime.timedelta(days=1),
                    anchor_date=datetime.datetime(2020, 1, 1),
                    timezone="UTC",
                ),
                active=True,
                max_scheduled_runs=None,
                parameters={},
                slug=None,
                created=datetime.datetime.now(),
                updated=datetime.datetime.now(),
            )
        ],
        tags=["transfer-test"],
        description="Test deployment for transfer",
        version="1.0.0",
        version_id=None,
        version_info=None,
        parameters={"test": "value"},
        path="./transfer-subdir",
        entrypoint="/transfer-file.py:flow",
        storage_document_id=uuid.uuid4(),
        infrastructure_document_id=None,
        work_queue_name="default",
        work_queue_id=uuid.uuid4(),
        work_pool_name="default-pool",
        parameter_openapi_schema=transfer_parameter_schema().model_dump_for_openapi(),
        paused=False,
        pull_steps=None,
        job_variables={},
        enforce_parameter_schema=True,
        concurrency_limit=None,
        concurrency_options=None,
        labels={},
        branch=None,
        base=None,
        root=None,
        status=None,
        created=datetime.datetime.now(),
        updated=datetime.datetime.now(),
        created_by=None,
        updated_by=None,
        last_polled=None,
    )


@pytest.fixture
async def transfer_deployment_with_infra(transfer_flow, transfer_block_document):
    """Create a deployment with infrastructure document for transfer testing."""
    from prefect.client.schemas.objects import DeploymentSchedule
    from prefect.client.schemas.schedules import IntervalSchedule

    # Create a simple DeploymentResponse object directly with infrastructure
    return DeploymentResponse(
        id=uuid.uuid4(),
        name=f"transfer-deployment-infra-{uuid.uuid4()}",
        flow_id=transfer_flow.id,
        schedules=[
            DeploymentSchedule(
                id=uuid.uuid4(),
                deployment_id=uuid.uuid4(),  # Will be overridden
                schedule=IntervalSchedule(
                    interval=datetime.timedelta(days=1),
                    anchor_date=datetime.datetime(2020, 1, 1),
                    timezone="UTC",
                ),
                active=True,
                max_scheduled_runs=None,
                parameters={},
                slug=None,
                created=datetime.datetime.now(),
                updated=datetime.datetime.now(),
            )
        ],
        tags=["transfer-test"],
        description="Test deployment with infrastructure",
        version="1.0.0",
        version_id=None,
        version_info=None,
        parameters={"test": "value"},
        path="./transfer-subdir",
        entrypoint="/transfer-file.py:flow",
        storage_document_id=uuid.uuid4(),
        infrastructure_document_id=transfer_block_document.id,  # Has infrastructure
        work_queue_name="default",
        work_queue_id=uuid.uuid4(),
        work_pool_name="default-pool",
        parameter_openapi_schema=transfer_parameter_schema().model_dump_for_openapi(),
        paused=False,
        pull_steps=None,
        job_variables={},
        enforce_parameter_schema=True,
        concurrency_limit=None,
        concurrency_options=None,
        labels={},
        branch=None,
        base=None,
        root=None,
        status=None,
        created=datetime.datetime.now(),
        updated=datetime.datetime.now(),
        created_by=None,
        updated_by=None,
        last_polled=None,
    )


# Variable fixtures
@pytest.fixture
async def transfer_variable(session: AsyncSession) -> Variable:
    """Create a variable for transfer testing."""
    variable = await models.variables.create_variable(
        session=session,
        variable=schemas.actions.VariableCreate(
            name=f"transfer-var-{uuid.uuid4()}",
            value="transfer-value",
            tags=["transfer-test"],
        ),
    )
    await session.commit()

    return Variable(
        id=variable.id,
        name=variable.name,
        value=variable.value,
        tags=variable.tags,
        created=variable.created,
        updated=variable.updated,
    )


# Client fixtures for isolated testing
@pytest.fixture
async def transfer_source_client(prefect_client):
    """Source client for transfer operations."""
    return prefect_client


@pytest.fixture
async def transfer_destination_client(prefect_client):
    """Destination client for transfer operations (same as source for testing)."""
    return prefect_client


# Global concurrency limit fixture
@pytest.fixture
async def transfer_global_concurrency_limit(session: AsyncSession):
    """Create a global concurrency limit for transfer testing."""
    from prefect.client.schemas.responses import GlobalConcurrencyLimitResponse
    from prefect.server import models

    limit = await models.concurrency_limits_v2.create_concurrency_limit(
        session=session,
        concurrency_limit=schemas.core.ConcurrencyLimitV2(
            name=f"transfer-limit-{uuid.uuid4()}",
            limit=5,
            active=True,
            active_slots=0,
        ),
    )
    await session.commit()

    # Convert to client schema object
    return GlobalConcurrencyLimitResponse(
        id=limit.id,
        name=limit.name,
        limit=limit.limit,
        active=limit.active,
        active_slots=limit.active_slots,
        slot_decay_per_second=limit.slot_decay_per_second,
        created=limit.created,
        updated=limit.updated,
    )


# Automation fixtures
@pytest.fixture
async def transfer_automation():
    """Create an automation for transfer testing."""
    from datetime import timedelta

    from prefect.events.actions import DoNothing
    from prefect.events.schemas.automations import Automation, EventTrigger, Posture
    from prefect.events.schemas.events import ResourceSpecification

    automation = Automation(
        id=uuid.uuid4(),
        name=f"transfer-automation-{uuid.uuid4()}",
        description="Test automation for transfer",
        enabled=True,
        tags=["transfer-test"],
        trigger=EventTrigger(
            expect={"prefect.flow-run.Completed"},
            match=ResourceSpecification(root={}),
            match_related=[],
            posture=Posture.Reactive,
            threshold=1,
            within=timedelta(seconds=30),
        ),
        actions=[DoNothing()],
        actions_on_trigger=[],
        actions_on_resolve=[],
    )
    return automation
