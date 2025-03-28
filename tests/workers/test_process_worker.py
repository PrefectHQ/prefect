import sys
import uuid
from datetime import timedelta
from pathlib import Path

import anyio
import anyio.abc
import pytest
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
from prefect.types._datetime import now
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
                scheduled_time=now("UTC") - timedelta(minutes=5)
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
async def flow_run_with_overrides(
    deployment: Deployment, prefect_client: PrefectClient
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id,
        state=State(
            type=client_schemas.StateType.SCHEDULED,
            state_details=client_schemas.StateDetails(
                scheduled_time=now("UTC") - timedelta(minutes=5)
            ),
        ),
    )
    await prefect_client.update_flow_run(
        flow_run_id=flow_run.id,
        job_variables={"working_dir": "/tmp/test"},
    )
    return await prefect_client.read_flow_run(flow_run.id)


@pytest.fixture
def mock_open_process(monkeypatch: pytest.MonkeyPatch):
    if sys.platform == "win32":
        monkeypatch.setattr(
            "prefect.utilities.processutils._open_anyio_process", AsyncMock()
        )
        prefect.utilities.processutils._open_anyio_process.return_value.terminate = (  # noqa
            MagicMock()
        )

        yield prefect.utilities.processutils._open_anyio_process  # noqa
    else:
        mock_open_process = AsyncMock()
        monkeypatch.setattr("anyio.open_process", mock_open_process)
        mock_open_process.return_value.terminate = MagicMock()  # noqa

        yield mock_open_process


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
    yield


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
        result = await worker.run(
            flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state is not None
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
        assert configuration.working_dir is None, (
            "This test assumes no configured working_dir"
        )
        result = await worker.run(
            flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

    call_kwargs = mock_runner_execute_flow_run.call_args[1]

    # should always execute in a tmp directory if working_dir not provided
    assert "tmp" in call_kwargs.pop("cwd")
    assert call_kwargs == dict(
        flow_run_id=flow_run.id,
        command=configuration.command,
        env=configuration.env,
        stream_output=configuration.stream_output,
        task_status=anyio.TASK_STATUS_IGNORED,
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
        task_status=anyio.TASK_STATUS_IGNORED,
    )
    assert configuration.env["NEW_ENV_VAR"] == "from_deployment"
    assert configuration.env["EXISTING_ENV_VAR"] == "from_os"


async def test_flow_run_without_job_vars(
    flow_run_with_deployment_overrides: FlowRun,
    work_pool_with_default_env: WorkPool,
    prefect_client: PrefectClient,
):
    assert flow_run_with_deployment_overrides.deployment_id is not None
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
    assert flow_run_with_overrides.deployment_id is not None
    assert flow_run_with_overrides.job_variables is not None
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
        config = await worker._get_configuration(flow_run_with_overrides)
        assert (
            str(config.working_dir)
            == flow_run_with_overrides.job_variables["working_dir"]
        )


async def test_flow_run_vars_and_deployment_vars_get_merged(
    flow_run_with_overrides: FlowRun,
    work_pool_with_default_env: WorkPool,
    session: AsyncSession,
):
    assert flow_run_with_overrides.deployment_id is not None
    assert flow_run_with_overrides.job_variables is not None
    await models.deployments.update_deployment(
        session=session,
        deployment_id=flow_run_with_overrides.deployment_id,
        deployment=DeploymentUpdate(
            job_variables={"stream_output": False},
        ),
    )
    await session.commit()

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
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

    assert flow_run.deployment_id is not None
    # Check mock_path is used after setting the override
    await prefect_client.update_deployment(
        deployment_id=flow_run.deployment_id,
        deployment=client_schemas.actions.DeploymentUpdate(
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

    assert flow_run.deployment_id is not None
    await prefect_client.update_deployment(
        deployment_id=flow_run.deployment_id,
        deployment=client_schemas.actions.DeploymentUpdate(
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
        assert configuration.working_dir is None, (
            "This test assumes no configured working_dir"
        )
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        call_kwargs = mock_runner_execute_flow_run.call_args[1]

        # should always execute in a tmp directory if working_dir not provided
        assert "tmp" in call_kwargs.pop("cwd")
        assert call_kwargs == dict(
            flow_run_id=flow_run.id,
            command=configuration.command,
            env=configuration.env,
            stream_output=configuration.stream_output,
            task_status=anyio.TASK_STATUS_IGNORED,
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
            task_status=anyio.TASK_STATUS_IGNORED,
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
