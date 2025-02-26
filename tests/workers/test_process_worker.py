import signal
import socket
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import call
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
from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.server import models
from prefect.server.database.orm_models import Flow
from prefect.server.schemas.actions import (
    DeploymentUpdate,
    WorkPoolCreate,
)
from prefect.states import Cancelled, Cancelling, Completed, Pending, Running, Scheduled
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
            "working_dir": "/deployment/tmp/test",
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
    flow_run, patch_run_process, process_work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()
    path_override_value = "/tmp/test"

    # Check default is not the mock_path
    patch_client(monkeypatch, overrides={})
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        worker._work_pool = process_work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["cwd"] != Path(path_override_value)

    # Check mock_path is used after setting the override
    patch_client(monkeypatch, overrides={"working_dir": path_override_value})
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        worker._work_pool = process_work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["cwd"] == Path(path_override_value)


async def test_process_worker_stream_output_override(
    flow_run, patch_run_process, process_work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()

    # Check default is True
    patch_client(monkeypatch, overrides={})
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        worker._work_pool = process_work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["stream_output"] is True

    # Check False is used after setting the override
    patch_client(monkeypatch, overrides={"stream_output": False})

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        worker._work_pool = process_work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["stream_output"] is False


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
            task_status=None,
        )


async def test_task_status_receives_pid(
    process_work_pool: WorkPool,
    patch_run_process: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
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


async def test_process_kill_mismatching_hostname(monkeypatch, process_work_pool):
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"not-{socket.gethostname()}:12345"

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        with pytest.raises(InfrastructureNotAvailable):
            await worker.kill_process(
                infrastructure_pid=infrastructure_pid,
            )

    os_kill.assert_not_called()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="SIGTERM/SIGKILL are only used in non-Windows environments",
)
async def test_process_kill_sends_sigterm_then_sigkill(monkeypatch, process_work_pool):
    patch_client(monkeypatch)
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 2

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        await worker.kill_process(
            infrastructure_pid=infrastructure_pid,
            grace_seconds=grace_seconds,
        )

    os_kill.assert_has_calls(
        [
            call(12345, signal.SIGTERM),
            call(12345, 0),
            call(12345, signal.SIGKILL),
        ]
    )


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="SIGTERM/SIGKILL are only used in non-Windows environments",
)
async def test_process_kill_early_return(monkeypatch, process_work_pool):
    patch_client(monkeypatch)
    os_kill = MagicMock(side_effect=[None, ProcessLookupError])
    anyio_sleep = AsyncMock()
    monkeypatch.setattr("os.kill", os_kill)
    monkeypatch.setattr("prefect.workers.process.anyio.sleep", anyio_sleep)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 30

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        await worker.kill_process(
            infrastructure_pid=infrastructure_pid,
            grace_seconds=grace_seconds,
        )

    os_kill.assert_has_calls(
        [
            call(12345, signal.SIGTERM),
            call(12345, 0),
        ]
    )

    anyio_sleep.assert_called_once_with(3)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="CTRL_BREAK_EVENT is only defined in Windows",
)
async def test_process_kill_windows_sends_ctrl_break(monkeypatch, process_work_pool):
    patch_client(monkeypatch)
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 15

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        await worker.kill_process(
            infrastructure_pid=infrastructure_pid,
            grace_seconds=grace_seconds,
        )

    os_kill.assert_called_once_with(12345, signal.CTRL_BREAK_EVENT)


def legacy_named_cancelling_state(**kwargs):
    return Cancelled(name="Cancelling", **kwargs)


class TestCancellation:
    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_called_for_cancelling_run(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        cancelling_constructor,
        work_pool,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        async with ProcessWorker(work_pool_name=work_pool.name) as worker:
            await worker.sync_with_backend()
            worker.cancel_run = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        worker.cancel_run.assert_awaited_once_with(flow_run)

    @pytest.mark.parametrize(
        "state",
        [
            # Name not "Cancelling"
            Cancelled(),
            # Name "Cancelling" but type not "Cancelled"
            Completed(name="Cancelling"),
            # Type not Cancelled
            Scheduled(),
            Pending(),
            Running(),
        ],
    )
    async def test_worker_cancel_run_not_called_for_other_states(
        self, prefect_client: PrefectClient, worker_deployment_wq1, state, work_pool
    ):
        await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=state,
        )

        async with ProcessWorker(work_pool_name=work_pool.name) as worker:
            await worker.sync_with_backend()
            worker.cancel_run = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        worker.cancel_run.assert_not_called()

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_called_for_cancelling_run_with_multiple_work_queues(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        cancelling_constructor,
        work_pool,
        work_queue_1,
        work_queue_2,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        async with ProcessWorker(
            work_pool_name=work_pool.name,
            work_queues=[work_queue_1.name, work_queue_2.name],
        ) as worker:
            await worker.sync_with_backend()
            worker.cancel_run = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        worker.cancel_run.assert_awaited_once_with(flow_run)

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_not_called_for_same_queue_names_in_different_work_pool(
        self,
        prefect_client: PrefectClient,
        deployment,
        cancelling_constructor,
        work_pool,
        work_queue_1,
        work_queue_2,
    ):
        # Update queue name, but not work pool name
        await prefect_client.update_deployment(
            deployment_id=deployment.id,
            deployment=client_schemas.actions.DeploymentUpdate(
                work_queue_name=work_queue_2.name
            ),
        )

        await prefect_client.create_flow_run_from_deployment(
            deployment.id,
            state=cancelling_constructor(),
        )

        async with ProcessWorker(
            work_pool_name=work_pool.name,
            work_queues=[work_queue_1.name],
        ) as worker:
            await worker.sync_with_backend()
            worker.cancel_run = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        worker.cancel_run.assert_not_called()

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_not_called_for_other_work_queues(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        cancelling_constructor,
        work_pool,
    ):
        await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        async with ProcessWorker(
            work_pool_name=work_pool.name,
            work_queues=[f"not-{worker_deployment_wq1.work_queue_name}"],
            prefetch_seconds=10,
        ) as worker:
            await worker.sync_with_backend()
            worker.cancel_run = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        worker.cancel_run.assert_not_called()

    # _______________________________________________________________________________

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_kills_run_with_infrastructure_pid(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        cancelling_constructor,
        work_pool,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        await prefect_client.update_flow_run(flow_run.id, infrastructure_pid="test")

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            worker.kill_process = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        worker.kill_process.assert_awaited_once_with(infrastructure_pid="test")

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_with_missing_infrastructure_pid(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        caplog,
        cancelling_constructor,
        work_pool,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            worker.kill_process = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        worker.kill_process.assert_not_awaited()

        # State name updated to prevent further attempts
        post_flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert post_flow_run.state.name == "Cancelled"

        # Information broadcasted to user in logs and state message
        assert (
            "does not have an infrastructure pid attached. Cancellation cannot be"
            " guaranteed." in caplog.text
        )
        assert (
            "missing infrastructure tracking information" in post_flow_run.state.message
        )

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_updates_state_type(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        cancelling_constructor,
        work_pool,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        await prefect_client.update_flow_run(
            flow_run.id, infrastructure_pid="test:test"
        )

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            worker.kill_process = AsyncMock()
            await worker.check_for_cancelled_flow_runs()

        post_flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert post_flow_run.state.type == StateType.CANCELLED

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    @pytest.mark.parametrize("infrastructure_pid", [None, "", "test"])
    async def test_worker_cancel_run_handles_missing_deployment(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        cancelling_constructor,
        work_pool,
        infrastructure_pid: str,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )
        await prefect_client.update_flow_run(
            flow_run.id, infrastructure_pid=infrastructure_pid
        )
        await prefect_client.delete_deployment(worker_deployment_wq1.id)

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            await worker.check_for_cancelled_flow_runs()

        post_flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert post_flow_run.state.type == StateType.CANCELLED

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_preserves_other_state_properties(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        cancelling_constructor,
        work_pool,
    ):
        expected_changed_fields = {"type", "name", "timestamp", "id", "state_details"}

        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(message="test"),
        )

        await prefect_client.update_flow_run(flow_run.id, infrastructure_pid="test")

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            await worker.check_for_cancelled_flow_runs()

        post_flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert post_flow_run.state.model_dump(
            exclude=expected_changed_fields
        ) == flow_run.state.model_dump(exclude=expected_changed_fields)

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_with_infrastructure_not_available_during_kill(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        caplog,
        cancelling_constructor,
        work_pool,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        await prefect_client.update_flow_run(flow_run.id, infrastructure_pid="test")

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            worker.kill_process = AsyncMock()
            worker.kill_process.side_effect = InfrastructureNotAvailable("Test!")
            await worker.check_for_cancelled_flow_runs()
            # Perform a second call to check that it is tracked locally that this worker
            # should not try again
            await worker.check_for_cancelled_flow_runs()

        # Only awaited once
        worker.kill_process.assert_awaited_once_with(infrastructure_pid="test")

        # State name not updated; other workers may attempt the kill
        post_flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert post_flow_run.state.name == "Cancelling"

        # Exception message is included with note on worker action
        assert "Test! Flow run cannot be cancelled by this worker." in caplog.text

        # State message is not changed
        assert post_flow_run.state.message is None

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_with_infrastructure_not_found_during_kill(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        caplog,
        cancelling_constructor,
        work_pool,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )

        await prefect_client.update_flow_run(flow_run.id, infrastructure_pid="test")

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            worker.kill_process = AsyncMock()
            worker.kill_process.side_effect = InfrastructureNotFound("Test!")
            await worker.check_for_cancelled_flow_runs()
            # Perform a second call to check that another cancellation attempt is not made
            await worker.check_for_cancelled_flow_runs()

        # Only awaited once
        worker.kill_process.assert_awaited_once_with(infrastructure_pid="test")

        # State name updated to prevent further attempts
        post_flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert post_flow_run.state.name == "Cancelled"

        # Exception message is included with note on worker action
        assert "Test! Marking flow run as cancelled." in caplog.text

        # No need for state message update
        assert post_flow_run.state.message is None

    @pytest.mark.parametrize(
        "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
    )
    async def test_worker_cancel_run_with_unknown_error_during_kill(
        self,
        prefect_client: PrefectClient,
        worker_deployment_wq1,
        caplog,
        cancelling_constructor,
        work_pool,
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(
            worker_deployment_wq1.id,
            state=cancelling_constructor(),
        )
        await prefect_client.update_flow_run(flow_run.id, infrastructure_pid="test")

        async with ProcessWorker(
            work_pool_name=work_pool.name, prefetch_seconds=10
        ) as worker:
            await worker.sync_with_backend()
            worker.kill_process = AsyncMock()
            worker.kill_process.side_effect = ValueError("Oh no!")
            await worker.check_for_cancelled_flow_runs()
            await anyio.sleep(0.5)
            await worker.check_for_cancelled_flow_runs()

        # Multiple attempts should be made
        worker.kill_process.assert_has_awaits(
            [
                call(infrastructure_pid="test"),
                call(infrastructure_pid="test"),
            ]
        )

        # State name not updated
        post_flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert post_flow_run.state.name == "Cancelling"

        assert (
            "Encountered exception while killing infrastructure for flow run"
            in caplog.text
        )
        assert "ValueError: Oh no!" in caplog.text
        assert "Traceback" in caplog.text
