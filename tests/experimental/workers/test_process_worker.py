import sys
from unittest.mock import AsyncMock, MagicMock

import anyio
import anyio.abc
import pendulum
import pytest

import prefect
from prefect import flow
from prefect.client.orion import OrionClient
from prefect.client.schemas import State
from prefect.experimental.workers.process import ProcessWorker, ProcessWorkerResult
from prefect.orion.schemas.states import StateDetails, StateType
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_WORKERS


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


async def test_worker_process_run_flow_run(flow_run, patch_run_process):
    mock: AsyncMock = patch_run_process()

    async with ProcessWorker(worker_pool_name="test-worker-pool") as worker:
        result = await worker.run(flow_run)

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        mock.assert_awaited_once
        assert mock.call_args.args == ([sys.executable, "-m", "prefect.engine"],)
        assert mock.call_args.kwargs["env"] == {"PREFECT__FLOW_RUN_ID": flow_run.id.hex}


async def test_process_created_then_marked_as_started(flow_run, mock_open_process):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    # By raising an exception when started is called we can assert the process
    # is opened before this time
    fake_status.started.side_effect = RuntimeError("Started called!")

    with pytest.raises(RuntimeError, match="Started called!"):
        async with ProcessWorker(worker_pool_name="test-worker-pool") as worker:
            await worker.run(flow_run=flow_run, task_status=fake_status)

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
    exit_code, help_message, caplog, patch_run_process, flow_run
):

    patch_run_process(returncode=exit_code)
    async with ProcessWorker(worker_pool_name="test-worker-pool") as worker:
        result = await worker.run(flow_run=flow_run)

        assert result.status_code == exit_code

        record = caplog.records[-1]
        assert record.levelname == "ERROR"
        assert help_message in record.message


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="subprocess.CREATE_NEW_PROCESS_GROUP is only defined in Windows",
)
async def test_windows_process_worker_run_sets_process_group_creation_flag(
    patch_run_process, flow_run
):
    mock = patch_run_process()

    async with ProcessWorker(worker_pool_name="test-worker-pool") as worker:
        await worker.run(flow_run=flow_run)

    mock.assert_awaited_once()
    (_, kwargs) = mock.call_args
    assert kwargs.get("creationflags") == mock.CREATE_NEW_PROCESS_GROUP


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="The asyncio.open_process_*.creationflags argument is only supported on Windows",
)
async def test_unix_process_worker_run_does_not_set_creation_flag(
    patch_run_process, flow_run
):
    mock = patch_run_process()
    async with ProcessWorker(worker_pool_name="test-worker-pool") as worker:
        await worker.run(flow_run=flow_run)

    mock.assert_awaited_once()
    (_, kwargs) = mock.call_args
    assert kwargs.get("creationflags") is None
