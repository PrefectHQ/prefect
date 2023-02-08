from pathlib import Path
from typing import Optional

import pendulum
import pydantic
import pytest
from pydantic import Field

import prefect.orion.schemas as schemas
from prefect.client.orion import OrionClient, get_client
from prefect.deployments import Deployment
from prefect.exceptions import ObjectNotFound
from prefect.experimental.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
)
from prefect.flows import flow
from prefect.orion import models
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_PATH,
)
from prefect.states import Completed, Pending, Running, Scheduled
from prefect.testing.utilities import AsyncMock


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


async def test_worker_creates_workflows_directory_during_setup(tmp_path: Path):
    await WorkerTestImpl(
        name="test",
        work_pool_name="test-work-pool",
        workflow_storage_path=tmp_path / "workflows",
    ).setup()
    assert (tmp_path / "workflows").exists()


async def test_worker_creates_work_pool_by_default_during_sync(
    orion_client: OrionClient,
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
    orion_client: OrionClient,
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
        (PREFECT_WORKER_WORKFLOW_STORAGE_PATH, "workflow_storage_path"),
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
    orion_client: OrionClient,
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


async def test_worker_applies_discovered_deployments(
    orion_client: OrionClient, flow_function, tmp_path: Path
):
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    deployment = await Deployment.build_from_flow(
        name="test-deployment", flow=flow_function
    )
    await deployment.to_yaml(workflows_path / "test-deployment.yaml")
    async with WorkerTestImpl(
        name="test",
        work_pool_name="test-work-pool",
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

    read_deployment = await orion_client.read_deployment_by_name(
        "client-test-flow/test-deployment"
    )
    assert read_deployment is not None


async def test_worker_applies_updates_to_deployments(
    orion_client: OrionClient, flow_function, tmp_path: Path, work_pool
):
    # create initial deployment manifest
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    deployment = await Deployment.build_from_flow(
        name="test-deployment", flow=flow_function, work_pool_name=work_pool.name
    )
    await deployment.to_yaml(workflows_path / "test-deployment.yaml")
    async with WorkerTestImpl(
        name="test",
        work_pool_name=work_pool.name,
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None

        # update deployment
        deployment.tags = ["new-tag"]
        deployment.timestamp = pendulum.now("UTC")
        await deployment.to_yaml(workflows_path / "test-deployment.yaml")

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None
        assert read_deployment.tags == ["new-tag"]


async def test_worker_does_not_apply_deployment_updates_for_old_timestamps(
    orion_client: OrionClient, flow_function, tmp_path: Path
):
    # create initial deployment manifest
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    deployment = await Deployment.build_from_flow(
        name="test-deployment", flow=flow_function
    )
    await deployment.to_yaml(workflows_path / "test-deployment.yaml")
    async with WorkerTestImpl(
        name="test",
        work_pool_name="test-work-pool",
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None

        # update deployment don't update timestamp
        deployment.tags = ["new-tag"]
        await deployment.to_yaml(workflows_path / "test-deployment.yaml")

        await worker.scan_storage_for_deployments()

        read_deployment = await orion_client.read_deployment_by_name(
            "client-test-flow/test-deployment"
        )
        assert read_deployment is not None
        assert read_deployment.tags == []


async def test_worker_does_not_raise_on_malformed_manifests(
    orion_client: OrionClient, tmp_path: Path
):
    workflows_path = tmp_path / "workflows"
    workflows_path.mkdir()
    (workflows_path / "test-deployment.yaml").write_text(
        "Ceci n'est pas un déploiement"
    )

    async with WorkerTestImpl(
        name="test",
        work_pool_name="test-work-pool",
        workflow_storage_path=workflows_path,
    ) as worker:

        await worker.scan_storage_for_deployments()

        assert len(await orion_client.read_deployments()) == 0


async def test_worker_with_work_queue(orion_client: OrionClient, deployment, work_pool):
    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
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


async def test_worker_with_work_queue_and_limit(
    orion_client: OrionClient, deployment, work_pool
):
    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
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
    orion_client: OrionClient, deployment, work_pool
):
    run_mock = AsyncMock()

    @flow
    def test_flow():
        pass

    create_run_with_deployment = (
        lambda state: orion_client.create_flow_run_from_deployment(
            deployment.id, state=state
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
        "job_configuration": {"command": "{{ command }}", "other": "{{ other }}"},
        "variables": {
            "properties": {
                "command": {
                    "type": "array",
                    "title": "Command",
                    "items": {"type": "string"},
                },
                "other": {"type": "string", "title": "Other"},
            },
            "required": [],
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
        "job_configuration": {"command": "{{ command }}", "other": "{{ other }}"},
        "variables": {
            "properties": {
                "command": {
                    "type": "array",
                    "title": "Command",
                    "items": {"type": "string"},
                },
                "other": {"type": "string", "title": "Other", "default": "woof"},
            },
            "required": [],
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

    assert worker._work_pool.base_job_template == worker_job_template


@pytest.mark.parametrize(
    "template,overrides,expected",
    [
        (
            {  # Base template with no overrides
                "job_configuration": {
                    "command": "{{ command }}",
                },
                "variables": {
                    "properties": {
                        "command": {
                            "type": "array",
                            "title": "Command",
                            "items": {"type": "string"},
                            "default": ["echo", "hello"],
                        }
                    },
                    "required": [],
                },
            },
            {},  # No overrides
            {  # Expected result
                "command": ["echo", "hello"],
            },
        ),
    ],
)
def test_base_job_configuration_from_template_and_overrides(
    template, overrides, expected
):
    """Test that the job configuration is correctly built from the template and overrides"""
    config = BaseJobConfiguration.from_template_and_overrides(
        base_job_template=template, deployment_overrides=overrides
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
                            "type": "array",
                            "title": "Command",
                            "items": {"type": "string"},
                            "default": ["echo", "hello"],
                        },
                    },
                    "required": [],
                },
            },
            {},  # No overrides
            {  # Expected result
                "command": ["echo", "hello"],
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
                "var1": "woof!",
                "var2": 42,
            },
        ),
    ],
)
def test_job_configuration_from_template_and_overrides(template, overrides, expected):
    """Test that the job configuration is correctly built from the template and overrides"""

    class ArbitraryJobConfiguration(BaseJobConfiguration):
        var1: str = Field(template="{{ var1 }}")
        var2: int = Field(template="{{ var2 }}")

    config = ArbitraryJobConfiguration.from_template_and_overrides(
        base_job_template=template, deployment_overrides=overrides
    )
    assert config.dict() == expected


@pytest.mark.parametrize(
    "falsey_value",
    [
        None,
        [],
    ],
)
def test_base_job_configuration_converts_falsey_values_to_none(falsey_value):
    """Test that valid falsey values are converted to None for `command`"""
    template = BaseJobConfiguration.from_template_and_overrides(
        base_job_template={
            "job_configuration": {
                "command": "{{ command }}",
            },
            "variables": {
                "properties": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                    },
                },
                "required": [],
            },
        },
        deployment_overrides={"command": falsey_value},
    )
    assert template.command is None


@pytest.mark.parametrize(
    "field_template_value,expected_final_template",
    [
        (
            "{{ var1 }}",
            {
                "command": "{{ command }}",
                "var1": "{{ var1 }}",
                "var2": "{{ var2 }}",
            },
        ),
        (
            None,
            {
                "command": "{{ command }}",
                "var1": "{{ var1 }}",
                "var2": "{{ var2 }}",
            },
        ),
        (
            "{{ dog }}",
            {
                "command": "{{ command }}",
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
