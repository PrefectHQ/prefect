from typing import Optional

import pendulum
import pydantic
import pytest
from pydantic import Field

import prefect
import prefect.server.schemas as schemas
from prefect.blocks.core import Block
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas import FlowRun
from prefect.exceptions import ObjectNotFound
from prefect.experimental.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
)
from prefect.flows import flow
from prefect.server import models
from prefect.server.schemas.core import Flow
from prefect.server.schemas.responses import DeploymentResponse
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    get_current_settings,
)
from prefect.states import Completed, Pending, Running, Scheduled
from prefect.testing.utilities import AsyncMock
from prefect.utilities.callables import parameter_schema


class WorkerTestImpl(BaseWorker):
    type = "test"
    job_configuration = BaseJobConfiguration

    async def run(self):
        pass

    async def verify_submitted_deployment(self, deployment):
        pass


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS


@pytest.fixture(autouse=True)
async def ensure_default_agent_pool_exists(session):
    # The default agent work pool is created by a migration, but is cleared on
    # consecutive test runs. This fixture ensures that the default agent work
    # pool exists before each test.
    default_work_pool = await models.workers.read_work_pool_by_name(
        session=session, work_pool_name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME
    )
    if default_work_pool is None:
        await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME, type="prefect-agent"
            ),
        )
        await session.commit()


@pytest.fixture
async def worker_deployment_wq1(
    session,
    flow,
    flow_function,
    work_queue_1,
):
    def hello(name: str):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment 1",
            tags=["test"],
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=pendulum.duration(days=1).as_timedelta(),
                anchor_date=pendulum.datetime(2020, 1, 1),
            ),
            path="./subdir",
            entrypoint="/file.py:flow",
            parameter_openapi_schema=parameter_schema(hello),
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
    def hello(name: str):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment 2",
            tags=["test"],
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=pendulum.duration(days=1).as_timedelta(),
                anchor_date=pendulum.datetime(2020, 1, 1),
            ),
            path="./subdir",
            entrypoint="/file.py:flow",
            parameter_openapi_schema=parameter_schema(hello),
            work_queue_id=work_queue_2.id,
        ),
    )
    await session.commit()
    return deployment


async def test_worker_creates_work_pool_by_default_during_sync(
    orion_client: PrefectClient,
):
    with pytest.raises(ObjectNotFound):
        await orion_client.read_work_pool("test-work-pool")

    async with WorkerTestImpl(
        name="test",
        work_pool_name="test-work-pool",
    ) as worker:
        await worker.sync_with_backend()
        worker_status = worker.get_status()
        assert worker_status["work_pool"]["name"] == "test-work-pool"

        work_pool = await orion_client.read_work_pool("test-work-pool")
        assert str(work_pool.id) == worker_status["work_pool"]["id"]


async def test_worker_does_not_creates_work_pool_when_create_pool_is_false(
    orion_client: PrefectClient,
):
    with pytest.raises(ObjectNotFound):
        await orion_client.read_work_pool("test-work-pool")

    async with WorkerTestImpl(
        name="test", work_pool_name="test-work-pool", create_pool_if_not_found=False
    ) as worker:
        await worker.sync_with_backend()
        worker_status = worker.get_status()
        assert worker_status["work_pool"] is None

    with pytest.raises(ObjectNotFound):
        await orion_client.read_work_pool("test-work-pool")


@pytest.mark.parametrize(
    "setting,attr",
    [
        (PREFECT_WORKER_PREFETCH_SECONDS, "prefetch_seconds"),
    ],
)
async def test_worker_respects_settings(setting, attr):
    assert (
        WorkerTestImpl(name="test", work_pool_name="test-work-pool").get_status()[
            "settings"
        ][attr]
        == setting.value()
    )


async def test_worker_sends_heartbeat_messages(
    orion_client: PrefectClient,
):
    async with WorkerTestImpl(name="test", work_pool_name="test-work-pool") as worker:
        await worker.sync_with_backend()

        workers = await orion_client.read_workers_for_work_pool(
            work_pool_name="test-work-pool"
        )
        assert len(workers) == 1
        first_heartbeat = workers[0].last_heartbeat_time
        assert first_heartbeat is not None

        await worker.sync_with_backend()

        workers = await orion_client.read_workers_for_work_pool(
            work_pool_name="test-work-pool"
        )
        second_heartbeat = workers[0].last_heartbeat_time
        assert second_heartbeat > first_heartbeat


async def test_worker_with_work_pool(
    orion_client: PrefectClient, worker_deployment_wq1, work_pool
):
    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id, state=state
        )
    )
    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await orion_client.create_flow_run(test_flow, state=Scheduled()),
    ]
    flow_run_ids = [run.id for run in flow_runs]

    async with WorkerTestImpl(work_pool_name=work_pool.name) as worker:
        submitted_flow_runs = await worker.get_and_submit_flow_runs()

    # Should only include scheduled runs in the past or next prefetch seconds
    # Should not include runs without deployments
    assert {flow_run.id for flow_run in submitted_flow_runs} == set(flow_run_ids[1:4])


async def test_worker_with_work_pool_and_work_queue(
    orion_client: PrefectClient,
    worker_deployment_wq1,
    worker_deployment_wq_2,
    work_queue_1,
    work_pool,
):
    @flow
    def test_flow():
        pass

    create_run_with_deployment_1 = (
        lambda state: orion_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id, state=state
        )
    )
    create_run_with_deployment_2 = (
        lambda state: orion_client.create_flow_run_from_deployment(
            worker_deployment_wq_2.id, state=state
        )
    )
    flow_runs = [
        await create_run_with_deployment_1(Pending()),
        await create_run_with_deployment_1(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment_1(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment_2(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment_2(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment_1(Running()),
        await create_run_with_deployment_1(Completed()),
        await orion_client.create_flow_run(test_flow, state=Scheduled()),
    ]
    flow_run_ids = [run.id for run in flow_runs]

    async with WorkerTestImpl(
        work_pool_name=work_pool.name, work_queues=[work_queue_1.name]
    ) as worker:
        submitted_flow_runs = await worker.get_and_submit_flow_runs()

    assert {flow_run.id for flow_run in submitted_flow_runs} == set(flow_run_ids[1:3])


async def test_worker_with_work_pool_and_limit(
    orion_client: PrefectClient, worker_deployment_wq1, work_pool
):
    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id, state=state
        )
    )
    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await orion_client.create_flow_run(test_flow, state=Scheduled()),
    ]
    flow_run_ids = [run.id for run in flow_runs]

    async with WorkerTestImpl(work_pool_name=work_pool.name, limit=2) as worker:
        worker._submit_run = AsyncMock()  # don't run anything

        submitted_flow_runs = await worker.get_and_submit_flow_runs()
        assert {flow_run.id for flow_run in submitted_flow_runs} == set(
            flow_run_ids[1:3]
        )

        submitted_flow_runs = await worker.get_and_submit_flow_runs()
        assert {flow_run.id for flow_run in submitted_flow_runs} == set(
            flow_run_ids[1:3]
        )

        worker._limiter.release_on_behalf_of(flow_run_ids[1])

        submitted_flow_runs = await worker.get_and_submit_flow_runs()
        assert {flow_run.id for flow_run in submitted_flow_runs} == set(
            flow_run_ids[1:4]
        )


async def test_worker_calls_run_with_expected_arguments(
    orion_client: PrefectClient, worker_deployment_wq1, work_pool, monkeypatch
):
    run_mock = AsyncMock()

    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id, state=state
        )
    )
    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await orion_client.create_flow_run(test_flow, state=Scheduled()),
    ]

    async with WorkerTestImpl(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        worker.run = run_mock  # don't run anything
        await worker.get_and_submit_flow_runs()

    assert run_mock.call_count == 3
    assert {call.kwargs["flow_run"].id for call in run_mock.call_args_list} == {
        fr.id for fr in flow_runs[1:4]
    }


async def test_worker_warns_when_running_a_flow_run_with_a_storage_block(
    orion_client: PrefectClient, deployment, work_pool, caplog
):
    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
        )
    )

    flow_run = await create_run_with_deployment(
        Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
    )

    async with WorkerTestImpl(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        await worker.get_and_submit_flow_runs()

    assert (
        f"Flow run {flow_run.id!r} was created from deployment"
        f" {deployment.name!r} which is configured with a storage block. Workers"
        " currently only support local storage. Please use an agent to execute this"
        " flow run."
        in caplog.text
    )

    flow_run = await orion_client.read_flow_run(flow_run.id)
    assert flow_run.state_name == "Scheduled"


async def test_base_worker_gets_job_configuration_when_syncing_with_backend_with_just_job_config(
    session, client
):
    """We don't really care how this happens as long as the worker winds up with a worker pool
    with a correct base_job_template when creating a new work pool"""

    class WorkerJobConfig(BaseJobConfiguration):
        other: Optional[str] = Field(template="{{other}}")

    # Add a job configuration for the worker (currently used to create template
    # if not found on the worker pool)
    WorkerTestImpl.job_configuration = WorkerJobConfig

    expected_job_template = {
        "job_configuration": {
            "command": "{{ command }}",
            "env": "{{ env }}",
            "labels": "{{ labels }}",
            "name": "{{ name }}",
            "other": "{{ other }}",
        },
        "variables": {
            "properties": {
                "command": {
                    "type": "string",
                    "title": "Command",
                    "description": (
                        "The command to use when starting a flow run. "
                        "In most cases, this should be left blank and the command "
                        "will be automatically generated by the worker."
                    ),
                },
                "env": {
                    "title": "Environment Variables",
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": (
                        "Environment variables to set when starting a flow run."
                    ),
                },
                "labels": {
                    "title": "Labels",
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": (
                        "Labels applied to infrastructure created by the worker using "
                        "this job configuration."
                    ),
                },
                "name": {
                    "type": "string",
                    "title": "Name",
                    "description": (
                        "Name given to infrastructure created by the worker using this "
                        "job configuration."
                    ),
                },
                "other": {"type": "string", "title": "Other"},
            },
            "type": "object",
        },
    }

    pool_name = "test-pool"

    # Create a new worker pool
    response = await client.post(
        "/work_pools/", json=dict(name=pool_name, type="test-type")
    )
    result = pydantic.parse_obj_as(schemas.core.WorkPool, response.json())
    model = await models.workers.read_work_pool(session=session, work_pool_id=result.id)
    assert model.name == pool_name

    # Create a worker with the new pool and sync with the backend
    worker = WorkerTestImpl(
        name="test",
        work_pool_name=pool_name,
    )
    async with get_client() as client:
        worker._client = client
        await worker.sync_with_backend()

    assert worker._work_pool.base_job_template == expected_job_template


async def test_base_worker_gets_job_configuration_when_syncing_with_backend_with_job_config_and_variables(
    session, client
):
    """We don't really care how this happens as long as the worker winds up with a worker pool
    with a correct base_job_template when creating a new work pool"""

    class WorkerJobConfig(BaseJobConfiguration):
        other: Optional[str] = Field(template="{{ other }}")

    class WorkerVariables(BaseVariables):
        other: Optional[str] = Field(default="woof")

    # Add a job configuration and variables for the worker (currently used to create template
    # if not found on the worker pool)
    WorkerTestImpl.job_configuration = WorkerJobConfig
    WorkerTestImpl.job_configuration_variables = WorkerVariables

    worker_job_template = {
        "job_configuration": {
            "command": "{{ command }}",
            "env": "{{ env }}",
            "labels": "{{ labels }}",
            "name": "{{ name }}",
            "other": "{{ other }}",
        },
        "variables": {
            "properties": {
                "command": {
                    "type": "string",
                    "title": "Command",
                    "description": (
                        "The command to use when starting a flow run. "
                        "In most cases, this should be left blank and the command "
                        "will be automatically generated by the worker."
                    ),
                },
                "env": {
                    "title": "Environment Variables",
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": (
                        "Environment variables to set when starting a flow run."
                    ),
                },
                "labels": {
                    "title": "Labels",
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": (
                        "Labels applied to infrastructure created by a worker."
                    ),
                },
                "name": {
                    "type": "string",
                    "title": "Name",
                    "description": "Name given to infrastructure created by a worker.",
                },
                "other": {"type": "string", "title": "Other", "default": "woof"},
            },
            "type": "object",
        },
    }

    pool_name = "test-pool"

    # Create a new worker pool
    response = await client.post(
        "/work_pools/", json=dict(name=pool_name, type="test-type")
    )
    result = pydantic.parse_obj_as(schemas.core.WorkPool, response.json())
    model = await models.workers.read_work_pool(session=session, work_pool_id=result.id)
    assert model.name == pool_name

    # Create a worker with the new pool and sync with the backend
    worker = WorkerTestImpl(
        name="test",
        work_pool_name=pool_name,
    )
    async with get_client() as client:
        worker._client = client
        await worker.sync_with_backend()

    assert (
        worker._work_pool.base_job_template
        == WorkerTestImpl.get_default_base_job_template()
    )


@pytest.mark.parametrize(
    "template,overrides,expected",
    [
        (
            {  # Base template with no overrides
                "job_configuration": {
                    "command": "{{ command }}",
                    "env": "{{ env }}",
                    "labels": "{{ labels }}",
                    "name": "{{ name }}",
                },
                "variables": {
                    "properties": {
                        "command": {
                            "type": "string",
                            "title": "Command",
                            "default": "echo hello",
                        },
                        "env": {
                            "title": "Environment Variables",
                            "type": "object",
                            "additionalProperties": {"type": "string"},
                            "description": (
                                "Environment variables to set when starting a flow run."
                            ),
                        },
                    },
                    "type": "object",
                },
            },
            {},  # No overrides
            {  # Expected result
                "command": "echo hello",
                "env": {},
                "labels": {},
                "name": None,
            },
        ),
    ],
)
async def test_base_job_configuration_from_template_and_overrides(
    template, overrides, expected
):
    """Test that the job configuration is correctly built from the template and overrides"""
    config = await BaseJobConfiguration.from_template_and_values(
        base_job_template=template, values=overrides
    )
    assert config.dict() == expected


@pytest.mark.parametrize(
    "template,overrides,expected",
    [
        (
            {  # Base template with no overrides
                "job_configuration": {
                    "var1": "{{ var1 }}",
                    "var2": "{{ var2 }}",
                },
                "variables": {
                    "properties": {
                        "var1": {
                            "type": "string",
                            "title": "Var1",
                            "default": "hello",
                        },
                        "var2": {
                            "type": "integer",
                            "title": "Var2",
                            "default": 42,
                        },
                    },
                    "required": [],
                },
            },
            {},  # No overrides
            {  # Expected result
                "command": None,
                "env": {},
                "labels": {},
                "name": None,
                "var1": "hello",
                "var2": 42,
            },
        ),
        (
            {  # Base template with no overrides, but unused variables
                "job_configuration": {
                    "var1": "{{ var1 }}",
                    "var2": "{{ var2 }}",
                },
                "variables": {
                    "properties": {
                        "var1": {
                            "type": "string",
                            "title": "Var1",
                            "default": "hello",
                        },
                        "var2": {
                            "type": "integer",
                            "title": "Var2",
                            "default": 42,
                        },
                        "var3": {
                            "type": "integer",
                            "title": "Var3",
                            "default": 21,
                        },
                    },
                    "required": [],
                },
            },
            {},  # No overrides
            {  # Expected result
                "command": None,
                "env": {},
                "labels": {},
                "name": None,
                "var1": "hello",
                "var2": 42,
            },
        ),
        (
            {  # Base template with command variables
                "job_configuration": {
                    "var1": "{{ var1 }}",
                    "var2": "{{ var2 }}",
                },
                "variables": {
                    "properties": {
                        "var1": {
                            "type": "string",
                            "title": "Var1",
                            "default": "hello",
                        },
                        "var2": {
                            "type": "integer",
                            "title": "Var2",
                            "default": 42,
                        },
                        "command": {
                            "type": "string",
                            "title": "Command",
                            "default": "echo hello",
                        },
                    },
                    "required": [],
                },
            },
            {},  # No overrides
            {  # Expected result
                "command": (
                    None
                ),  # command variable is not used in the job configuration
                "env": {},
                "labels": {},
                "name": None,
                "var1": "hello",
                "var2": 42,
            },
        ),
        (
            {  # Base template with var1 overridden
                "job_configuration": {
                    "var1": "{{ var1 }}",
                    "var2": "{{ var2 }}",
                },
                "variables": {
                    "properties": {
                        "var1": {
                            "type": "string",
                            "title": "Var1",
                            "default": "hello",
                        },
                        "var2": {
                            "type": "integer",
                            "title": "Var2",
                            "default": 42,
                        },
                    },
                },
                "required": [],
            },
            {"var1": "woof!"},  # var1 overridden
            {  # Expected result
                "command": None,
                "env": {},
                "labels": {},
                "name": None,
                "var1": "woof!",
                "var2": 42,
            },
        ),
        (
            {  # Base template with var1 overridden and var1 required
                "job_configuration": {
                    "var1": "{{ var1 }}",
                    "var2": "{{ var2 }}",
                },
                "variables": {
                    "properties": {
                        "var1": {
                            "type": "string",
                            "title": "Var1",
                        },
                        "var2": {
                            "type": "integer",
                            "title": "Var2",
                            "default": 42,
                        },
                    },
                },
                "required": ["var1"],
            },
            {"var1": "woof!"},  # var1 overridden
            {  # Expected result
                "command": None,
                "env": {},
                "labels": {},
                "name": None,
                "var1": "woof!",
                "var2": 42,
            },
        ),
    ],
)
async def test_job_configuration_from_template_and_overrides(
    template, overrides, expected
):
    """Test that the job configuration is correctly built from the template and overrides"""

    class ArbitraryJobConfiguration(BaseJobConfiguration):
        var1: str = Field(template="{{ var1 }}")
        var2: int = Field(template="{{ var2 }}")

    config = await ArbitraryJobConfiguration.from_template_and_values(
        base_job_template=template, values=overrides
    )
    assert config.dict() == expected


async def test_job_configuration_from_template_and_overrides_with_nested_variables():
    template = {
        "job_configuration": {
            "config": {
                "var1": "{{ var1 }}",
                "var2": "{{ var2 }}",
            }
        },
        "variables": {
            "properties": {
                "var1": {
                    "type": "string",
                    "title": "Var1",
                },
                "var2": {
                    "type": "integer",
                    "title": "Var2",
                    "default": 42,
                },
            },
        },
        "required": ["var1"],
    }

    class ArbitraryJobConfiguration(BaseJobConfiguration):
        config: dict = Field(template={"var1": "{{ var1 }}", "var2": "{{ var2 }}"})

    config = await ArbitraryJobConfiguration.from_template_and_values(
        base_job_template=template, values={"var1": "woof!"}
    )
    assert config.dict() == {
        "command": None,
        "env": {},
        "labels": {},
        "name": None,
        "config": {
            "var1": "woof!",
            "var2": 42,
        },
    }


async def test_job_configuration_from_template_and_overrides_with_hard_coded_primitives():
    template = {
        "job_configuration": {"config": {"var1": 1, "var2": 1.1, "var3": True}},
        "variables": {},
    }

    class ArbitraryJobConfiguration(BaseJobConfiguration):
        config: dict = Field(template={"var1": 1, "var2": 1.1, "var3": True})

    config = await ArbitraryJobConfiguration.from_template_and_values(
        base_job_template=template, values={}
    )
    assert config.dict() == {
        "command": None,
        "env": {},
        "labels": {},
        "name": None,
        "config": {"var1": 1, "var2": 1.1, "var3": True},
    }


async def test_job_configuration_from_template_overrides_with_block():
    class ArbitraryBlock(Block):
        a: int
        b: str

    template = {
        "job_configuration": {
            "var1": "{{ var1 }}",
            "arbitrary_block": "{{ arbitrary_block }}",
        },
        "variables": {
            "properties": {
                "var1": {
                    "type": "string",
                },
                "arbitrary_block": {},
            },
            "definitions": {
                "ArbitraryBlock": {
                    "title": "ArbitraryBlock",
                    "type": "object",
                    "properties": {
                        "a": {
                            "title": "A",
                            "type": "number",
                        },
                        "b": {
                            "title": "B",
                            "type": "string",
                        },
                    },
                    "required": ["a", "b"],
                    "block_type_slug": "arbitrary_block",
                    "secret_fields": [],
                    "block_schema_references": {},
                },
            },
            "required": ["var1", "arbitrary_block"],
        },
    }

    class ArbitraryJobConfiguration(BaseJobConfiguration):
        var1: str
        arbitrary_block: ArbitraryBlock

    block_id = await ArbitraryBlock(a=1, b="hello").save(name="arbitrary-block")

    config = await ArbitraryJobConfiguration.from_template_and_values(
        base_job_template=template,
        values={
            "var1": "woof!",
            "arbitrary_block": {"$ref": {"block_document_id": block_id}},
        },
    )

    assert config.dict() == {
        "command": None,
        "env": {},
        "labels": {},
        "name": None,
        "var1": "woof!",
        # block_type_slug is added by Block.dict()
        "arbitrary_block": {"a": 1, "b": "hello", "block_type_slug": "arbitraryblock"},
    }


async def test_job_configuration_from_template_and_overrides_with_variables_in_a_list():
    template = {
        "job_configuration": {"config": ["{{ var1 }}", "{{ var2 }}"]},
        "variables": {
            "properties": {
                "var1": {
                    "type": "string",
                    "title": "Var1",
                },
                "var2": {
                    "type": "integer",
                    "title": "Var2",
                    "default": 42,
                },
            },
        },
        "required": ["var1"],
    }

    class ArbitraryJobConfiguration(BaseJobConfiguration):
        config: list = Field(template=["{{ var1 }}", "{{ var2 }}"])

    config = await ArbitraryJobConfiguration.from_template_and_values(
        base_job_template=template, values={"var1": "woof!"}
    )
    assert config.dict() == {
        "command": None,
        "env": {},
        "labels": {},
        "name": None,
        "config": ["woof!", 42],
    }


@pytest.mark.parametrize(
    "falsey_value",
    [
        None,
        "",
    ],
)
async def test_base_job_configuration_converts_falsey_values_to_none(falsey_value):
    """Test that valid falsey values are converted to None for `command`"""
    template = await BaseJobConfiguration.from_template_and_values(
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
        values={"command": falsey_value},
    )
    assert template.command is None


@pytest.mark.parametrize(
    "field_template_value,expected_final_template",
    [
        (
            "{{ var1 }}",
            {
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
                "var1": "{{ var1 }}",
                "var2": "{{ var2 }}",
            },
        ),
        (
            None,
            {
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
                "var1": "{{ var1 }}",
                "var2": "{{ var2 }}",
            },
        ),
        (
            "{{ dog }}",
            {
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
                "var1": "{{ dog }}",
                "var2": "{{ var2 }}",
            },
        ),
    ],
)
def test_job_configuration_produces_correct_json_template(
    field_template_value, expected_final_template
):
    class ArbitraryJobConfiguration(BaseJobConfiguration):
        var1: str = Field(template=field_template_value)
        var2: int = Field(template="{{ var2 }}")

    template = ArbitraryJobConfiguration.json_template()
    assert template == expected_final_template


class TestWorkerProperties:
    def test_defaults(self):
        class WorkerImplNoCustomization(BaseWorker):
            type = "test-no-customization"

            async def run(self):
                pass

            async def verify_submitted_deployment(self, deployment):
                pass

        assert WorkerImplNoCustomization.get_logo_url() == ""
        assert WorkerImplNoCustomization.get_documentation_url() == ""
        assert WorkerImplNoCustomization.get_description() == ""
        assert WorkerImplNoCustomization.get_default_base_job_template() == {
            "job_configuration": {
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "string",
                        "title": "Command",
                        "description": (
                            "The command to use when starting a flow run. "
                            "In most cases, this should be left blank and the command "
                            "will be automatically generated by the worker."
                        ),
                    },
                    "env": {
                        "title": "Environment Variables",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Environment variables to set when starting a flow run."
                        ),
                    },
                    "labels": {
                        "title": "Labels",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Labels applied to infrastructure created by the worker"
                            " using this job configuration."
                        ),
                    },
                    "name": {
                        "type": "string",
                        "title": "Name",
                        "description": (
                            "Name given to infrastructure created by the worker using "
                            "this job configuration."
                        ),
                    },
                },
                "type": "object",
            },
        }

    def test_custom_logo_url(self):
        class WorkerImplWithLogoUrl(BaseWorker):
            type = "test-with-logo-url"
            job_configuration = BaseJobConfiguration

            _logo_url = "https://example.com/logo.png"

            async def run(self):
                pass

            async def verify_submitted_deployment(self, deployment):
                pass

        assert WorkerImplWithLogoUrl.get_logo_url() == "https://example.com/logo.png"

    def test_custom_documentation_url(self):
        class WorkerImplWithDocumentationUrl(BaseWorker):
            type = "test-with-documentation-url"
            job_configuration = BaseJobConfiguration

            _documentation_url = "https://example.com/docs"

            async def run(self):
                pass

            async def verify_submitted_deployment(self, deployment):
                pass

        assert (
            WorkerImplWithDocumentationUrl.get_documentation_url()
            == "https://example.com/docs"
        )

    def test_custom_description(self):
        class WorkerImplWithDescription(BaseWorker):
            type = "test-with-description"
            job_configuration = BaseJobConfiguration

            _description = "Custom Worker Description"

            async def run(self):
                pass

            async def verify_submitted_deployment(self, deployment):
                pass

        assert (
            WorkerImplWithDescription.get_description() == "Custom Worker Description"
        )

    def test_custom_base_job_configuration(self):
        class CustomBaseJobConfiguration(BaseJobConfiguration):
            var1: str = Field(template="{{ var1 }}")
            var2: int = Field(template="{{ var2 }}")

        class CustomBaseVariables(BaseVariables):
            var1: str = Field(default=...)
            var2: int = Field(default=1)

        class WorkerImplWithCustomBaseJobConfiguration(BaseWorker):
            type = "test-with-base-job-configuration"
            job_configuration = CustomBaseJobConfiguration
            job_configuration_variables = CustomBaseVariables

            async def run(self):
                pass

            async def verify_submitted_deployment(self, deployment):
                pass

        assert WorkerImplWithCustomBaseJobConfiguration.get_default_base_job_template() == {
            "job_configuration": {
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
                "var1": "{{ var1 }}",
                "var2": "{{ var2 }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "title": "Command",
                        "type": "string",
                        "description": (
                            "The command to use when starting a flow run. "
                            "In most cases, this should be left blank and the command "
                            "will be automatically generated by the worker."
                        ),
                    },
                    "env": {
                        "title": "Environment Variables",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Environment variables to set when starting a flow run."
                        ),
                    },
                    "labels": {
                        "title": "Labels",
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Labels applied to infrastructure created by a worker."
                        ),
                    },
                    "name": {
                        "title": "Name",
                        "type": "string",
                        "description": (
                            "Name given to infrastructure created by a worker."
                        ),
                    },
                    "var1": {"title": "Var1", "type": "string"},
                    "var2": {"title": "Var2", "type": "integer", "default": 1},
                },
                "required": ["var1"],
                "type": "object",
            },
        }


class TestPrepareForFlowRun:
    @pytest.fixture
    def job_config(self):
        return BaseJobConfiguration(
            env={"MY_VAR": "foo"},
            labels={"my-label": "foo"},
            name="my-job-name",
        )

    @pytest.fixture
    def flow_run(self):
        return FlowRun(name="my-flow-run-name")

    @pytest.fixture
    def deployment(self):
        return DeploymentResponse(name="my-deployment-name")

    @pytest.fixture
    def flow(self):
        return Flow(name="my-flow-name")

    def test_prepare_for_flow_run_without_deployment_and_flow(
        self, job_config, flow_run
    ):
        job_config.prepare_for_flow_run(flow_run)

        assert job_config.env == {
            **get_current_settings().to_environment_variables(exclude_unset=True),
            "MY_VAR": "foo",
            "PREFECT__FLOW_RUN_ID": flow_run.id.hex,
        }
        assert job_config.labels == {
            "my-label": "foo",
            "prefect.io/flow-run-id": str(flow_run.id),
            "prefect.io/flow-run-name": flow_run.name,
            "prefect.io/version": prefect.__version__,
        }
        assert job_config.name == "my-job-name"
        assert job_config.command == "python -m prefect.engine"

    def test_prepare_for_flow_run_with_deployment_and_flow(
        self, job_config, flow_run, deployment, flow
    ):
        job_config.prepare_for_flow_run(flow_run, deployment=deployment, flow=flow)

        assert job_config.env == {
            **get_current_settings().to_environment_variables(exclude_unset=True),
            "MY_VAR": "foo",
            "PREFECT__FLOW_RUN_ID": flow_run.id.hex,
        }
        assert job_config.labels == {
            "my-label": "foo",
            "prefect.io/flow-run-id": str(flow_run.id),
            "prefect.io/flow-run-name": flow_run.name,
            "prefect.io/version": prefect.__version__,
            "prefect.io/deployment-id": str(deployment.id),
            "prefect.io/deployment-name": deployment.name,
            "prefect.io/flow-id": str(flow.id),
            "prefect.io/flow-name": flow.name,
        }
        assert job_config.name == "my-job-name"
        assert job_config.command == "python -m prefect.engine"
