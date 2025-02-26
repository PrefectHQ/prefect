import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

import anyio
import anyio.abc
import pendulum
import pytest
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import prefect
from prefect import flow
from prefect.client import schemas as client_schemas
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import State
from prefect.client.schemas.objects import Deployment, FlowRun, StateType, WorkPool
from prefect.server import models
from prefect.server.database.orm_models import Flow
from prefect.server.schemas.actions import (
    DeploymentUpdate,
    WorkPoolCreate,
)
from prefect.testing.utilities import AsyncMock, MagicMock
from prefect.types import DateTime
from prefect.workers.process import (
    ProcessWorker,
    ProcessWorkerResult,
)


@flow
def example_process_worker_flow():
    return 1


@pytest.fixture
def patch_run_process(monkeypatch: pytest.MonkeyPatch):
    def patch_run_process(returncode: int = 0, pid: int = 1000):
        mock_run_process = AsyncMock()
        mock_process = MagicMock()
        mock_process.returncode = returncode
        mock_process.pid = pid
        mock_run_process.return_value = mock_process

        monkeypatch.setattr(
            "prefect.workers.process.Runner._run_process", mock_run_process
        )

        return mock_run_process

    return patch_run_process


@pytest.fixture
async def deployment(prefect_client: PrefectClient, flow: Flow):
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow.id,
        name=f"test-process-worker-deployment-{uuid.uuid4()}",
        path=str(
            prefect.__development_base_path__
            / "tests"
            / "test-projects"
            / "import-project"
        ),
        entrypoint="my_module/flow.py:test_flow",
    )
    return await prefect_client.read_deployment(deployment_id)


@pytest.fixture
async def flow_run(deployment: Deployment, prefect_client: PrefectClient):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id,
        state=State(
            type=client_schemas.StateType.SCHEDULED,
            state_details=client_schemas.StateDetails(
                scheduled_time=pendulum.now("utc").subtract(minutes=5)
            ),
        ),
    )

    return flow_run


@pytest.fixture
async def deployment_with_overrides(prefect_client: PrefectClient, flow: Flow):
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow.id,
        name=f"test-process-worker-deployment-{uuid.uuid4()}",
        path=str(
            prefect.__development_base_path__
            / "tests"
            / "test-projects"
            / "import-project"
        ),
        entrypoint="my_module/flow.py:test_flow",
        job_variables={
            "command": "echo hello",
            "env": {"NEW_ENV_VAR": "from_deployment"},
            "working_dir": "/tmp/test",
        },
    )
    deployment = await prefect_client.read_deployment(deployment_id)
    return deployment


@pytest.fixture
async def flow_run_with_deployment_overrides(
    deployment_with_overrides: Deployment, prefect_client: PrefectClient
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_with_overrides.id,
        state=State(type=client_schemas.StateType.SCHEDULED),
    )
    return flow_run


@pytest.fixture
async def flow_run_with_overrides(deployment, prefect_client: PrefectClient):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id,
        state=State(
            type=client_schemas.StateType.SCHEDULED,
            state_details=client_schemas.StateDetails(
                scheduled_time=pendulum.now("utc").subtract(minutes=5)
            ),
        ),
    )
    await prefect_client.update_flow_run(
        flow_run_id=flow_run.id,
        job_variables={"working_dir": "/tmp/test"},
    )
    return await prefect_client.read_flow_run(flow_run.id)


@pytest.fixture
def mock_open_process(monkeypatch):
    if sys.platform == "win32":
        monkeypatch.setattr(
            "prefect.utilities.processutils._open_anyio_process", AsyncMock()
        )
        prefect.utilities.processutils._open_anyio_process.return_value.terminate = (  # noqa
            MagicMock()
        )

        yield prefect.utilities.processutils._open_anyio_process  # noqa
    else:
        monkeypatch.setattr("anyio.open_process", AsyncMock())
        anyio.open_process.return_value.terminate = MagicMock()  # noqa

        yield anyio.open_process


@pytest.fixture
def mock_runner_execute_flow_run(monkeypatch: pytest.MonkeyPatch):
    mock_process = MagicMock(returncode=0, pid=1000)
    mock_execute_flow_run = AsyncMock()
    mock_execute_flow_run.return_value = mock_process
    monkeypatch.setattr(
        "prefect.runner.runner.Runner.execute_flow_run", mock_execute_flow_run
    )
    return mock_execute_flow_run


@pytest.fixture(autouse=True)
def tmp_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(str(tmp_path))


def patch_client(monkeypatch, overrides: Optional[Dict[str, Any]] = None):
    """Patches client to return a mock deployment and mock flow with the specified overrides"""

    class MockDeployment(BaseModel):
        id: UUID = uuid.uuid4()
        job_variables: Dict[str, Any] = overrides or {}
        name: str = "test-deployment"
        updated: DateTime = pendulum.now("utc")

    class MockFlow(BaseModel):
        id: UUID = uuid.uuid4()
        name: str = "test-flow"

    class MockWorkPool(BaseModel):
        id: UUID = uuid.uuid4()
        name: str = "test-work-pool"
        type: str = "process"
        description: str = "None"
        base_job_template: dict[str, Any] = {}

    mock_get_client = MagicMock()
    mock_client = MagicMock()
    mock_read_deployment = AsyncMock()
    mock_read_deployment.return_value = MockDeployment()
    mock_read_flow = AsyncMock()
    mock_read_flow.return_value = MockFlow()
    mock_read_work_pool = AsyncMock()
    mock_read_work_pool.return_value = MockWorkPool()
    mock_update_work_pool = AsyncMock()
    mock_update_work_pool.return_value = MockWorkPool()
    mock_client.read_deployment = mock_read_deployment
    mock_client.read_flow = mock_read_flow
    mock_get_client.return_value = mock_client
    mock_client.read_work_pool = mock_read_work_pool
    mock_client.update_work_pool = mock_update_work_pool
    mock_client.send_worker_heartbeat = AsyncMock()
    monkeypatch.setattr("prefect.workers.base.get_client", mock_get_client)

    return mock_read_deployment


@pytest.fixture
async def process_work_pool(session: AsyncSession):
    job_template = ProcessWorker.get_default_base_job_template()

    wp = await models.workers.create_work_pool(
        session=session,
        work_pool=WorkPoolCreate.model_construct(
            _fields_set=WorkPoolCreate.model_fields_set,
            name="test-worker-pool",
            type="test",
            description="None",
            base_job_template=job_template,
        ),
    )
    await session.commit()
    return wp


@pytest.fixture
async def work_pool_with_default_env(session: AsyncSession):
    job_template = ProcessWorker.get_default_base_job_template()
    job_template["variables"]["properties"]["env"]["default"] = {
        "CONFIG_ENV_VAR": "from_job_configuration"
    }
    wp = await models.workers.create_work_pool(
        session=session,
        work_pool=WorkPoolCreate.model_construct(
            _fields_set=WorkPoolCreate.model_fields_set,
            name="wp-1",
            type="test",
            description="None",
            base_job_template=job_template,
        ),
    )
    await session.commit()
    return wp


async def test_worker_process_run_flow_run(
    flow_run: FlowRun,
    process_work_pool: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
    prefect_client: PrefectClient,
):
    async with ProcessWorker(
        work_pool_name=process_work_pool.name,
    ) as worker:
        worker._work_pool = process_work_pool
        result = await worker.run(
            flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state.type == StateType.COMPLETED


async def test_worker_process_run_flow_run_with_env_variables_job_config_defaults(
    flow_run: FlowRun,
    mock_runner_execute_flow_run: MagicMock,
    work_pool_with_default_env: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EXISTING_ENV_VAR", "from_os")

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        configuration = await worker._get_configuration(flow_run)
        result = await worker.run(
            flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

    mock_runner_execute_flow_run.assert_awaited_once_with(
        flow_run_id=flow_run.id,
        command=configuration.command,
        cwd=configuration.working_dir,
        env=configuration.env,
        stream_output=configuration.stream_output,
        task_status=None,
    )
    assert configuration.env["CONFIG_ENV_VAR"] == "from_job_configuration"
    assert configuration.env["EXISTING_ENV_VAR"] == "from_os"


async def test_worker_process_run_flow_run_with_env_variables_from_overrides(
    flow_run_with_deployment_overrides: FlowRun,
    mock_runner_execute_flow_run: MagicMock,
    work_pool_with_default_env: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EXISTING_ENV_VAR", "from_os")

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        configuration = await worker._get_configuration(
            flow_run_with_deployment_overrides
        )
        result = await worker.run(
            flow_run_with_deployment_overrides,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

    mock_runner_execute_flow_run.assert_awaited_once_with(
        flow_run_id=flow_run_with_deployment_overrides.id,
        command=configuration.command,
        cwd=configuration.working_dir,
        env=configuration.env,
        stream_output=configuration.stream_output,
        task_status=None,
    )
    assert configuration.env["NEW_ENV_VAR"] == "from_deployment"
    assert configuration.env["EXISTING_ENV_VAR"] == "from_os"


async def test_flow_run_without_job_vars(
    flow_run_with_deployment_overrides: FlowRun,
    work_pool_with_default_env: WorkPool,
    prefect_client: PrefectClient,
):
    deployment = await prefect_client.read_deployment(
        flow_run_with_deployment_overrides.deployment_id
    )

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        configuration = await worker._get_configuration(
            flow_run_with_deployment_overrides
        )
        assert str(configuration.working_dir) == deployment.job_variables["working_dir"]


async def test_flow_run_vars_take_precedence(
    flow_run_with_overrides: FlowRun,
    work_pool_with_default_env: WorkPool,
    session: AsyncSession,
):
    await models.deployments.update_deployment(
        session=session,
        deployment_id=flow_run_with_overrides.deployment_id,
        deployment=DeploymentUpdate(
            job_variables={"working_dir": "/deployment/tmp/test"},
        ),
    )
    await session.commit()

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        worker._work_pool = work_pool_with_default_env
        config = await worker._get_configuration(flow_run_with_overrides)
        assert (
            str(config.working_dir)
            == flow_run_with_overrides.job_variables["working_dir"]
        )


async def test_flow_run_vars_and_deployment_vars_get_merged(
    deployment,
    flow_run_with_overrides,
    work_pool_with_default_env,
    session: AsyncSession,
):
    await models.deployments.update_deployment(
        session=session,
        deployment_id=deployment.id,
        deployment=DeploymentUpdate(
            job_variables={"stream_output": False},
        ),
    )
    await session.commit()

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        worker._work_pool = work_pool_with_default_env
        config = await worker._get_configuration(flow_run_with_overrides)
        assert (
            str(config.working_dir)
            == flow_run_with_overrides.job_variables["working_dir"]
        )
        assert config.stream_output is False


async def test_process_worker_working_dir_override(
    flow_run: FlowRun,
    mock_runner_execute_flow_run: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
):
    path_override_value = "/tmp/test"

    # Check default is not the mock_path
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker._get_configuration(flow_run)
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock_runner_execute_flow_run.call_args.kwargs["cwd"] != Path(
            path_override_value
        )

    # Check mock_path is used after setting the override
    await prefect_client.update_deployment(
        deployment_id=flow_run.deployment_id,
        deployment=DeploymentUpdate(
            job_variables={"working_dir": path_override_value},
        ),
    )
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker._get_configuration(flow_run)
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock_runner_execute_flow_run.call_args.kwargs["cwd"] == Path(
            path_override_value
        )


async def test_process_worker_stream_output_override(
    flow_run: FlowRun,
    mock_runner_execute_flow_run: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
):
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker._get_configuration(flow_run)
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock_runner_execute_flow_run.call_args.kwargs["stream_output"] is True

    await prefect_client.update_deployment(
        deployment_id=flow_run.deployment_id,
        deployment=DeploymentUpdate(
            job_variables={"stream_output": False},
        ),
    )

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker._get_configuration(flow_run)
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock_runner_execute_flow_run.call_args.kwargs["stream_output"] is False


async def test_process_worker_executes_flow_run_with_runner(
    flow_run: FlowRun,
    mock_runner_execute_flow_run: MagicMock,
    process_work_pool: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
):
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker._get_configuration(flow_run)
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        mock_runner_execute_flow_run.assert_awaited_once_with(
            flow_run_id=flow_run.id,
            command=configuration.command,
            cwd=configuration.working_dir,
            env=configuration.env,
            stream_output=configuration.stream_output,
            task_status=None,
        )


async def test_process_worker_command_override(
    deployment_with_overrides: Deployment,
    flow_run_with_deployment_overrides: FlowRun,
    mock_runner_execute_flow_run: MagicMock,
    process_work_pool: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
):
    override_command = deployment_with_overrides.job_variables["command"]
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker._get_configuration(
            flow_run_with_deployment_overrides
        )
        result = await worker.run(
            flow_run=flow_run_with_deployment_overrides,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        mock_runner_execute_flow_run.assert_awaited_once_with(
            flow_run_id=flow_run_with_deployment_overrides.id,
            command=override_command,
            cwd=configuration.working_dir,
            env=configuration.env,
            stream_output=configuration.stream_output,
            task_status=None,
        )


async def test_task_status_receives_pid(
    process_work_pool: WorkPool,
    flow_run: FlowRun,
):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
            task_status=fake_status,
        )

        fake_status.started.assert_called_once_with(int(result.identifier))
