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
from exceptiongroup import ExceptionGroup, catch
from pydantic import BaseModel
from pydantic_extra_types.pendulum_dt import DateTime
from sqlalchemy.ext.asyncio import AsyncSession

import prefect
from prefect import flow
from prefect.client import schemas as client_schemas
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import State
from prefect.exceptions import InfrastructureNotAvailable
from prefect.server import models
from prefect.server.schemas.actions import (
    DeploymentUpdate,
    WorkPoolCreate,
)
from prefect.testing.utilities import AsyncMock, MagicMock
from prefect.workers.process import (
    ProcessJobConfiguration,
    ProcessWorker,
    ProcessWorkerResult,
)


@flow
def example_process_worker_flow():
    return 1


@pytest.fixture
def patch_run_process(monkeypatch):
    def patch_run_process(returncode=0, pid=1000):
        mock_run_process = AsyncMock()
        mock_run_process.return_value.returncode = returncode
        mock_run_process.return_value.pid = pid
        monkeypatch.setattr(prefect.workers.process, "run_process", mock_run_process)

        return mock_run_process

    return patch_run_process


@pytest.fixture
async def flow_run(prefect_client: PrefectClient):
    flow_run = await prefect_client.create_flow_run(
        flow=example_process_worker_flow,
        state=State(
            type=client_schemas.StateType.SCHEDULED,
            state_details=client_schemas.StateDetails(
                scheduled_time=pendulum.now("utc").subtract(minutes=5)
            ),
        ),
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

    mock_get_client = MagicMock()
    mock_client = MagicMock()
    mock_read_deployment = AsyncMock()
    mock_read_deployment.return_value = MockDeployment()
    mock_read_flow = AsyncMock()
    mock_read_flow.return_value = MockFlow()
    mock_client.read_deployment = mock_read_deployment
    mock_client.read_flow = mock_read_flow
    mock_get_client.return_value = mock_client

    monkeypatch.setattr("prefect.workers.base.get_client", mock_get_client)

    return mock_read_deployment


@pytest.fixture
async def work_pool(session: AsyncSession):
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
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()
    patch_client(monkeypatch)

    async with ProcessWorker(
        work_pool_name=work_pool.name,
    ) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        mock.assert_awaited_once
        assert mock.call_args.args == (
            [
                sys.executable,
                "-m",
                "prefect.engine",
            ],
        )
        assert mock.call_args.kwargs["env"]["PREFECT__FLOW_RUN_ID"] == str(flow_run.id)


async def test_worker_process_run_flow_run_with_env_variables_job_config_defaults(
    flow_run, patch_run_process, work_pool_with_default_env, monkeypatch
):
    monkeypatch.setenv("EXISTING_ENV_VAR", "from_os")
    mock: AsyncMock = patch_run_process()
    patch_client(monkeypatch)

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        worker._work_pool = work_pool_with_default_env
        result = await worker.run(
            flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        mock.assert_awaited_once
        assert mock.call_args.args == (
            [
                sys.executable,
                "-m",
                "prefect.engine",
            ],
        )
        assert mock.call_args.kwargs["env"]["PREFECT__FLOW_RUN_ID"] == str(flow_run.id)
        assert mock.call_args.kwargs["env"]["EXISTING_ENV_VAR"] == "from_os"
        assert (
            mock.call_args.kwargs["env"]["CONFIG_ENV_VAR"] == "from_job_configuration"
        )


async def test_worker_process_run_flow_run_with_env_variables_from_overrides(
    flow_run, patch_run_process, work_pool_with_default_env, monkeypatch
):
    monkeypatch.setenv("EXISTING_ENV_VAR", "from_os")
    mock: AsyncMock = patch_run_process()
    patch_client(monkeypatch, overrides={"env": {"NEW_ENV_VAR": "from_deployment"}})

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        worker._work_pool = work_pool_with_default_env
        result = await worker.run(
            flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        mock.assert_awaited_once
        assert mock.call_args.args == (
            [
                sys.executable,
                "-m",
                "prefect.engine",
            ],
        )
        assert mock.call_args.kwargs["env"]["PREFECT__FLOW_RUN_ID"] == str(flow_run.id)
        assert mock.call_args.kwargs["env"]["EXISTING_ENV_VAR"] == "from_os"
        assert mock.call_args.kwargs["env"]["NEW_ENV_VAR"] == "from_deployment"


async def test_flow_run_without_job_vars(
    flow_run,
    work_pool_with_default_env,
    monkeypatch,
):
    deployment_job_vars = {"working_dir": "/deployment/tmp/test"}
    patch_client(monkeypatch, overrides=deployment_job_vars)

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        worker._work_pool = work_pool_with_default_env
        config = await worker._get_configuration(flow_run)
        assert str(config.working_dir) == deployment_job_vars["working_dir"]


async def test_flow_run_vars_take_precedence(
    deployment,
    flow_run_with_overrides,
    work_pool_with_default_env,
    session: AsyncSession,
):
    await models.deployments.update_deployment(
        session=session,
        deployment_id=deployment.id,
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


async def test_process_created_then_marked_as_started(
    flow_run, mock_open_process, work_pool, monkeypatch
):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    # By raising an exception when started is called we can assert the process
    # is opened before this time
    fake_status.started.side_effect = RuntimeError("Started called!")
    patch_client(monkeypatch)
    fake_configuration = MagicMock()
    fake_configuration.command = "echo hello"

    def handle_exception_group(excgrp: ExceptionGroup):
        assert len(excgrp.exceptions) == 1
        assert isinstance(excgrp.exceptions[0], RuntimeError)
        assert str(excgrp.exceptions[0]) == "Started called!"

    with catch(  # should be superseded by `ExceptionGroup` once we're 3.11+
        {RuntimeError: handle_exception_group}  # type: ignore
    ):  # see https://github.com/agronholm/anyio/blob/master/docs/migration.rst#task-groups-now-wrap-single-exceptions-in-groups # noqa F821
        async with ProcessWorker(
            work_pool_name=work_pool.name,
        ) as worker:
            worker._work_pool = work_pool
            await worker.run(
                flow_run=flow_run,
                configuration=fake_configuration,
                task_status=fake_status,
            )

    fake_status.started.assert_called_once()
    mock_open_process.assert_awaited_once()


@pytest.mark.parametrize(
    "exit_code,help_message",
    [
        (-9, "This indicates that the process exited due to a SIGKILL signal"),
        (
            247,
            "This indicates that the process was terminated due to high memory usage.",
        ),
    ],
)
async def test_process_worker_logs_exit_code_help_message(
    exit_code,
    help_message,
    caplog,
    patch_run_process,
    flow_run,
    work_pool,
    monkeypatch,
):
    patch_client(monkeypatch)
    patch_run_process(returncode=exit_code)
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert result.status_code == exit_code

        record = caplog.records[-1]
        assert record.levelname == "ERROR"
        assert help_message in record.message


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="subprocess.CREATE_NEW_PROCESS_GROUP is only defined in Windows",
)
async def test_windows_process_worker_run_sets_process_group_creation_flag(
    patch_run_process, flow_run, work_pool, monkeypatch
):
    mock = patch_run_process()
    patch_client(monkeypatch)

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

    mock.assert_awaited_once()
    (_, kwargs) = mock.call_args
    assert kwargs.get("creationflags") == mock.CREATE_NEW_PROCESS_GROUP


@pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "The asyncio.open_process_*.creationflags argument is only supported on Windows"
    ),
)
async def test_unix_process_worker_run_does_not_set_creation_flag(
    patch_run_process, flow_run, work_pool, monkeypatch
):
    mock = patch_run_process()
    patch_client(monkeypatch)
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

    mock.assert_awaited_once()
    (_, kwargs) = mock.call_args
    assert kwargs.get("creationflags") is None


async def test_process_worker_working_dir_override(
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()
    path_override_value = "/tmp/test"

    # Check default is not the mock_path
    patch_client(monkeypatch, overrides={})
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["cwd"] != Path(path_override_value)

    # Check mock_path is used after setting the override
    patch_client(monkeypatch, overrides={"working_dir": path_override_value})
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["cwd"] == Path(path_override_value)


async def test_process_worker_stream_output_override(
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()

    # Check default is True
    patch_client(monkeypatch, overrides={})
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["stream_output"] is True

    # Check False is used after setting the override
    patch_client(monkeypatch, overrides={"stream_output": False})

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["stream_output"] is False


async def test_process_worker_uses_correct_default_command(
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()
    correct_default = [
        sys.executable,
        "-m",
        "prefect.engine",
    ]
    patch_client(monkeypatch)

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.args == (correct_default,)


async def test_process_worker_command_override(
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()
    override_command = "echo hello world"
    override = {"command": override_command}
    patch_client(monkeypatch, overrides=override)

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.args == (override_command.split(" "),)


async def test_task_status_receives_infrastructure_pid(
    work_pool, patch_run_process, monkeypatch, flow_run
):
    patch_client(monkeypatch)
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
            task_status=fake_status,
        )

        hostname = socket.gethostname()
        fake_status.started.assert_called_once_with(f"{hostname}:{result.identifier}")


async def test_process_kill_mismatching_hostname(monkeypatch, work_pool):
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"not-{socket.gethostname()}:12345"

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        with pytest.raises(InfrastructureNotAvailable):
            await worker.kill_infrastructure(
                infrastructure_pid=infrastructure_pid,
                configuration=ProcessJobConfiguration(),
            )

    os_kill.assert_not_called()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="SIGTERM/SIGKILL are only used in non-Windows environments",
)
async def test_process_kill_sends_sigterm_then_sigkill(monkeypatch, work_pool):
    patch_client(monkeypatch)
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 2

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        await worker.kill_infrastructure(
            infrastructure_pid=infrastructure_pid,
            grace_seconds=grace_seconds,
            configuration=ProcessJobConfiguration(),
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
async def test_process_kill_early_return(monkeypatch, work_pool):
    patch_client(monkeypatch)
    os_kill = MagicMock(side_effect=[None, ProcessLookupError])
    anyio_sleep = AsyncMock()
    monkeypatch.setattr("os.kill", os_kill)
    monkeypatch.setattr("prefect.workers.process.anyio.sleep", anyio_sleep)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 30

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        await worker.kill_infrastructure(
            infrastructure_pid=infrastructure_pid,
            grace_seconds=grace_seconds,
            configuration=ProcessJobConfiguration(),
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
async def test_process_kill_windows_sends_ctrl_break(monkeypatch, work_pool):
    patch_client(monkeypatch)
    os_kill = MagicMock()
    monkeypatch.setattr("os.kill", os_kill)

    infrastructure_pid = f"{socket.gethostname()}:12345"
    grace_seconds = 15

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        await worker.kill_infrastructure(
            infrastructure_pid=infrastructure_pid,
            grace_seconds=grace_seconds,
            configuration=ProcessJobConfiguration(),
        )

    os_kill.assert_called_once_with(12345, signal.CTRL_BREAK_EVENT)
