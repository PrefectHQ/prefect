import os
import signal
import sys
import tempfile
from unittest.mock import ANY

import anyio
import pytest

import prefect
from prefect.client.orchestration import PrefectClient
from prefect.settings import (
    PREFECT_WORKER_PREFETCH_SECONDS,
    temporary_settings,
    get_current_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import MagicMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.processutils import open_process


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_run_once_with_name():
    invoke_and_assert(
        command=[
            "worker",
            "start",
            "--run-once",
            "-p",
            "test-work-pool",
            "-n",
            "test-worker",
            "-t",
            "process",
        ],
        expected_code=0,
        expected_output_contains=[
            "Worker 'test-worker' started!",
            "Worker 'test-worker' stopped!",
        ],
    )


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_start_worker_creates_work_pool(prefect_client: PrefectClient):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "worker",
            "start",
            "--run-once",
            "-p",
            "not-yet-created-pool",
            "-t",
            "process",
        ],
        expected_code=0,
        expected_output_contains=["Worker", "stopped!", "Worker", "started!"],
    )

    work_pool = await prefect_client.read_work_pool("not-yet-created-pool")
    assert work_pool is not None
    assert work_pool.name == "not-yet-created-pool"
    assert work_pool.default_queue_id is not None


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_work_queue_names(monkeypatch, process_work_pool):
    mock_worker = MagicMock()
    monkeypatch.setattr(prefect.cli.worker, "lookup_type", lambda x, y: mock_worker)
    invoke_and_assert(
        command=[
            "worker",
            "start",
            "-p",
            process_work_pool.name,
            "--work-queue",
            "a",
            "-q",
            "b",
            "--run-once",
        ],
        expected_code=0,
    )
    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name=process_work_pool.name,
        work_queues=["a", "b"],
        prefetch_seconds=ANY,
        limit=None,
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_prefetch_seconds(monkeypatch):
    mock_worker = MagicMock()
    monkeypatch.setattr(prefect.cli.worker, "lookup_type", lambda x, y: mock_worker)
    invoke_and_assert(
        command=[
            "worker",
            "start",
            "--prefetch-seconds",
            "30",
            "-p",
            "test",
            "--run-once",
            "-t",
            "process",
        ],
        expected_code=0,
    )
    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name="test",
        work_queues=[],
        prefetch_seconds=30,
        limit=None,
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_prefetch_seconds_from_setting_by_default(monkeypatch):
    mock_worker = MagicMock()
    monkeypatch.setattr(prefect.cli.worker, "lookup_type", lambda x, y: mock_worker)
    with temporary_settings({PREFECT_WORKER_PREFETCH_SECONDS: 100}):
        invoke_and_assert(
            command=[
                "worker",
                "start",
                "-p",
                "test",
                "--run-once",
                "-t",
                "process",
            ],
            expected_code=0,
        )
    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name="test",
        work_queues=[],
        prefetch_seconds=100,
        limit=None,
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_limit(monkeypatch):
    mock_worker = MagicMock()
    monkeypatch.setattr(prefect.cli.worker, "lookup_type", lambda x, y: mock_worker)
    invoke_and_assert(
        command=[
            "worker",
            "start",
            "-l",
            "5",
            "-p",
            "test",
            "--run-once",
            "-t",
            "process",
        ],
        expected_code=0,
    )
    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name="test",
        work_queues=[],
        prefetch_seconds=10,
        limit=5,
    )


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_worker_joins_existing_pool(work_pool, prefect_client: PrefectClient):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "worker",
            "start",
            "--run-once",
            "-p",
            work_pool.name,
            "-n",
            "test-worker",
            "-t",
            "process",
        ],
        expected_code=0,
        expected_output_contains=[
            "Worker 'test-worker' started!",
            "Worker 'test-worker' stopped!",
        ],
    )

    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=work_pool.name
    )
    assert workers[0].name == "test-worker"


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_worker_discovers_work_pool_type(
    process_work_pool, prefect_client: PrefectClient
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "worker",
            "start",
            "--run-once",
            "-p",
            process_work_pool.name,
            "-n",
            "test-worker",
        ],
        expected_code=0,
        expected_output_contains=[
            (
                f"Discovered worker type {process_work_pool.type!r} for work pool"
                f" {process_work_pool.name!r}."
            ),
            "Worker 'test-worker' started!",
            "Worker 'test-worker' stopped!",
        ],
    )

    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=process_work_pool.name
    )
    assert workers[0].name == "test-worker"


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_start_worker_without_type_creates_process_work_pool(
    prefect_client: PrefectClient,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "worker",
            "start",
            "--run-once",
            "-p",
            "not-here",
            "-n",
            "test-worker",
        ],
        expected_code=0,
        expected_output_contains=[
            (
                "Work pool 'not-here' does not exist and no worker type was"
                " provided. Starting a process worker..."
            ),
            "Worker 'test-worker' started!",
            "Worker 'test-worker' stopped!",
        ],
    )

    workers = await prefect_client.read_workers_for_work_pool(work_pool_name="not-here")
    assert workers[0].name == "test-worker"


POLL_INTERVAL = 0.5
STARTUP_TIMEOUT = 20
SHUTDOWN_TIMEOUT = 5


async def safe_shutdown(process):
    try:
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await process.wait()
    except TimeoutError:
        # try twice in case process.wait() hangs
        with anyio.fail_after(SHUTDOWN_TIMEOUT):
            await process.wait()


@pytest.fixture(scope="function")
async def worker_process(use_hosted_api_server):
    """
    Runs an agent listening to all queues.
    Yields:
        The anyio.Process.
    """
    out = tempfile.TemporaryFile()  # capture output for test assertions

    # Will connect to the same database as normal test clients
    async with open_process(
        command=[
            "prefect",
            "worker",
            "start",
            "--type",
            "process",
            "--pool",
            "my-pool",
            "--name",
            "test-worker",
        ],
        stdout=out,
        stderr=out,
        env={**os.environ, **get_current_settings().to_environment_variables()},
    ) as process:
        process.out = out

        for _ in range(int(STARTUP_TIMEOUT / POLL_INTERVAL)):
            await anyio.sleep(POLL_INTERVAL)
            if out.tell() > 400:
                await anyio.sleep(2)
                break

        assert out.tell() > 400, "The worker did not start up in time"
        assert process.returncode is None, "The worker failed to start up"

        # Yield to the consuming tests
        yield process

        # Then shutdown the process
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        out.close()


class TestWorkerSignalForwarding:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm(self, worker_process):
        worker_process.send_signal(signal.SIGINT)
        await safe_shutdown(worker_process)
        worker_process.out.seek(0)
        out = worker_process.out.read().decode()

        assert "Sending SIGINT" in out, (
            "When sending a SIGINT, the main process should receive a SIGINT."
            f" Output:\n{out}"
        )
        assert "Worker 'test-worker' stopped!" in out, (
            "When sending a SIGINT, the main process should shutdown gracefully."
            f" Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_directly(self, worker_process):
        worker_process.send_signal(signal.SIGTERM)
        await safe_shutdown(worker_process)
        worker_process.out.seek(0)
        out = worker_process.out.read().decode()

        assert "Sending SIGINT" in out, (
            "When sending a SIGTERM, the main process should receive a SIGINT."
            f" Output:\n{out}"
        )
        assert "Worker 'test-worker' stopped!" in out, (
            "When sending a SIGTERM, the main process should shutdown gracefully."
            f" Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm_then_sigkill(self, worker_process):
        worker_process.send_signal(signal.SIGINT)
        await anyio.sleep(0.1)  # some time needed for the recursive signal handler
        worker_process.send_signal(signal.SIGINT)
        await safe_shutdown(worker_process)
        worker_process.out.seek(0)
        out = worker_process.out.read().decode()

        assert (
            # either the main PID is still waiting for shutdown, so forwards the SIGKILL
            "Sending SIGKILL" in out
            # or SIGKILL came too late, and the main PID is already closing
            or "KeyboardInterrupt" in out
            or "Worker 'test-worker' stopped!" in out
            or "Aborted." in out
        ), (
            "When sending two SIGINT shortly after each other, the main process should"
            f" first receive a SIGINT and then a SIGKILL. Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigterm_sends_sigterm_then_sigkill(self, worker_process):
        worker_process.send_signal(signal.SIGTERM)
        await anyio.sleep(0.1)  # some time needed for the recursive signal handler
        worker_process.send_signal(signal.SIGTERM)
        await safe_shutdown(worker_process)
        worker_process.out.seek(0)
        out = worker_process.out.read().decode()

        assert (
            # either the main PID is still waiting for shutdown, so forwards the SIGKILL
            "Sending SIGKILL" in out
            # or SIGKILL came too late, and the main PID is already closing
            or "KeyboardInterrupt" in out
            or "Worker 'test-worker' stopped!" in out
            or "Aborted." in out
        ), (
            "When sending two SIGTERM shortly after each other, the main process should"
            f" first receive a SIGINT and then a SIGKILL. Output:\n{out}"
        )

    @pytest.mark.skipif(
        sys.platform != "win32",
        reason="CTRL_BREAK_EVENT is only defined in Windows",
    )
    async def test_sends_ctrl_break_win32(self, worker_process):
        worker_process.send_signal(signal.SIGINT)
        await safe_shutdown(worker_process)
        worker_process.out.seek(0)
        out = worker_process.out.read().decode()

        assert "Sending CTRL_BREAK_EVENT" in out, (
            "When sending a SIGINT, the main process should send a CTRL_BREAK_EVENT to"
            f" the worker subprocess. Output:\n{out}"
        )
