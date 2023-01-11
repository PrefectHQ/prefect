import sys

import anyio
import anyio.abc
import pendulum
import pytest
from pydantic import BaseModel

import prefect
from prefect import flow
from prefect.client.orion import OrionClient
from prefect.client.schemas import State
from prefect.experimental.workers.process import ProcessWorker, ProcessWorkerResult
from prefect.orion.schemas.core import WorkPool
from prefect.orion.schemas.states import StateDetails, StateType
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_WORKERS
from prefect.testing.utilities import AsyncMock, MagicMock


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS


@flow
def example_flow():
    return 1


@pytest.fixture
def patch_run_process(monkeypatch):
    def patch_run_process(returncode=0, pid=1000):
        mock_run_process = AsyncMock()
        mock_run_process.return_value.returncode = returncode
        mock_run_process.return_value.pid = pid
        monkeypatch.setattr(
            prefect.experimental.workers.process, "run_process", mock_run_process
        )

        return mock_run_process

    return patch_run_process


@pytest.fixture
async def flow_run(orion_client: OrionClient):
    flow_run = await orion_client.create_flow_run(
        flow=example_flow,
        state=State(
            type=StateType.SCHEDULED,
            state_details=StateDetails(
                scheduled_time=pendulum.now("utc").subtract(minutes=5)
            ),
        ),
    )

    return flow_run


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


def patch_read_deployment(monkeypatch, overrides: dict = None):
    """Patches client._read_deployment to return a mock deployment with the specified overrides"""

    class MockDeployment(BaseModel):
        infra_overrides: dict = overrides or {}

    mock_get_client = MagicMock()
    mock_client = MagicMock()
    mock_read_deployment = AsyncMock()
    mock_read_deployment.return_value = MockDeployment()
    mock_client.read_deployment = mock_read_deployment
    mock_get_client.return_value = mock_client

    monkeypatch.setattr("prefect.experimental.workers.base.get_client", mock_get_client)

    return mock_read_deployment


@pytest.fixture
def work_pool():
    job_template = {
        "job_configuration": {
            "command": "{{ command }}",
            "working_dir": "{{ working_dir }}",
            "stream_output": "{{ stream_output }}",
        },
        "variables": {
            "properties": {
                "command": {
                    "type": "array",
                    "title": "Command",
                    "items": {"type": "string"},
                },
                "working_dir": {
                    "type": "string",
                    "title": "Working Directory",
                    "default": None,
                },
                "stream_output": {
                    "type": "boolean",
                    "title": "Stream Output",
                    "default": True,
                },
            },
            "required": [],
        },
    }

    work_pool = MagicMock(spec=WorkPool)
    work_pool.name = "test-worker-pool"
    work_pool.base_job_template = job_template
    return work_pool


async def test_worker_process_run_flow_run(
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()
    read_deployment_mock = patch_read_deployment(monkeypatch)

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
        assert mock.call_args.args == ([sys.executable, "-m", "prefect.engine"],)
        assert mock.call_args.kwargs["env"] == {"PREFECT__FLOW_RUN_ID": flow_run.id.hex}


async def test_process_created_then_marked_as_started(
    flow_run, mock_open_process, work_pool, monkeypatch
):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    # By raising an exception when started is called we can assert the process
    # is opened before this time
    fake_status.started.side_effect = RuntimeError("Started called!")
    read_deployment_mock = patch_read_deployment(monkeypatch)
    fake_configuration = MagicMock()
    fake_configuration.command = ["echo", "hello"]
    with pytest.raises(RuntimeError, match="Started called!"):
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

    read_deployment_mock = patch_read_deployment(monkeypatch)
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
    read_deployment_mock = patch_read_deployment(monkeypatch)

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
    reason="The asyncio.open_process_*.creationflags argument is only supported on Windows",
)
async def test_unix_process_worker_run_does_not_set_creation_flag(
    patch_run_process, flow_run, work_pool, monkeypatch
):
    mock = patch_run_process()
    read_deployment_mock = patch_read_deployment(monkeypatch)
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
    read_deployment_mock = patch_read_deployment(monkeypatch, overrides={})
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["cwd"] != path_override_value

    # Check mock_path is used after setting the override
    read_deployment_mock = patch_read_deployment(
        monkeypatch, overrides={"working_dir": path_override_value}
    )
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["cwd"] == path_override_value


async def test_process_worker_stream_output_override(
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()

    # Check default is True
    read_deployment_mock = patch_read_deployment(monkeypatch, overrides={})
    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["stream_output"] == True

    # Check False is used after setting the override
    read_deployment_mock = patch_read_deployment(
        monkeypatch, overrides={"stream_output": False}
    )

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.kwargs["stream_output"] == False


async def test_process_worker_uses_correct_default_command(
    flow_run, patch_run_process, work_pool, monkeypatch
):
    mock: AsyncMock = patch_run_process()
    correct_default = [sys.executable, "-m", "prefect.engine"]
    read_deployment_mock = patch_read_deployment(monkeypatch)

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
    override_command = ["echo", "hello", "world"]
    override = {"command": override_command}
    read_deployment_mock = patch_read_deployment(monkeypatch, overrides=override)

    async with ProcessWorker(work_pool_name=work_pool.name) as worker:
        worker._work_pool = work_pool
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker._get_configuration(flow_run),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock.call_args.args == (override_command,)
