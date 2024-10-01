import os
import signal
import sys
from pathlib import Path
from unittest.mock import ANY

import anyio
import httpx
import pytest
import readchar
import respx
from anyio.streams.text import TextReceiveStream
from typer import Exit

import prefect
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_WORKER_PREFETCH_SECONDS,
    get_current_settings,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock, MagicMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.workers.base import BaseJobConfiguration, BaseWorker


async def _receive_stream(stream) -> str:
    out = ""
    while True:
        try:
            line = await TextReceiveStream(stream).receive()
            out += line
        except anyio.EndOfStream:
            break
    return out


class MockKubernetesWorker(BaseWorker):
    type = "kubernetes-test"
    job_configuration = BaseJobConfiguration

    async def run(self):
        pass


@pytest.fixture
def interactive_console(monkeypatch):
    monkeypatch.setattr("prefect.cli.worker.is_interactive", lambda: True)

    # `readchar` does not like the fake stdin provided by typer isolation so we provide
    # a version that does not require a fd to be attached
    def readchar():
        sys.stdin.flush()
        position = sys.stdin.tell()
        if not sys.stdin.read():
            print("TEST ERROR: CLI is attempting to read input but stdin is empty.")
            raise Exit(-2)
        else:
            sys.stdin.seek(position)
        return sys.stdin.read(1)

    monkeypatch.setattr("readchar._posix_read.readchar", readchar)


@pytest.fixture
async def kubernetes_work_pool(prefect_client: PrefectClient):
    work_pool = await prefect_client.create_work_pool(
        work_pool=WorkPoolCreate(name="test-k8s-work-pool", type="kubernetes-test")
    )

    with respx.mock(
        assert_all_mocked=False, base_url=PREFECT_API_URL.value()
    ) as respx_mock:
        respx_mock.get("/csrf-token", params={"client": ANY}).pass_through()
        respx_mock.route(path__startswith="/work_pools/").pass_through()
        respx_mock.get("/collections/views/aggregate-worker-metadata").mock(
            return_value=httpx.Response(
                200,
                json={
                    "prefect": {
                        "prefect-agent": {
                            "type": "prefect-agent",
                            "default_base_job_configuration": {},
                        }
                    },
                    "prefect-kubernetes": {
                        "kubernetes-test": {
                            "type": "kubernetes-test",
                            "default_base_job_configuration": {},
                        }
                    },
                },
            )
        )

        yield work_pool


@pytest.fixture
def mock_worker(monkeypatch):
    mock_worker_start = AsyncMock()
    mock_worker = MagicMock()
    mock_worker.return_value.start = mock_worker_start
    monkeypatch.setattr(prefect.cli.worker, "lookup_type", lambda x, y: mock_worker)
    return mock_worker


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
async def test_start_worker_creates_work_pool_with_base_config(
    prefect_client: PrefectClient,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "worker",
            "start",
            "--run-once",
            "--pool",
            "my-cool-pool",
            "--type",
            "process",
            "--base-job-template",
            Path(__file__).parent / "base-job-templates" / "process-worker.json",
        ],
        expected_code=0,
        expected_output_contains=["Worker", "stopped!", "Worker", "started!"],
    )

    work_pool = await prefect_client.read_work_pool("my-cool-pool")
    assert work_pool is not None
    assert work_pool.name == "my-cool-pool"
    assert work_pool.default_queue_id is not None
    assert work_pool.base_job_template == {
        "job_configuration": {"command": "{{ command }}", "name": "{{ name }}"},
        "variables": {
            "properties": {
                "command": {
                    "description": "Command to run.",
                    "title": "Command",
                    "type": "string",
                },
                "name": {
                    "description": "Description.",
                    "title": "Name",
                    "type": "string",
                },
            },
            "type": "object",
        },
    }


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_work_queue_names(mock_worker, process_work_pool):
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
        heartbeat_interval_seconds=30,
        base_job_template=None,
    )
    mock_worker.return_value.start.assert_awaited_once_with(
        run_once=True, with_healthcheck=False, printer=ANY
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_specified_work_queues_paused(mock_worker, process_work_pool):
    invoke_and_assert(
        command=[
            "work-queue",
            "pause",
            "default",
            "--pool",
            process_work_pool.name,
        ],
        expected_code=0,
        expected_output_contains=[
            f"Work queue 'default' in work pool {process_work_pool.name!r} paused"
        ],
    )

    invoke_and_assert(
        command=[
            "worker",
            "start",
            "-p",
            process_work_pool.name,
            "--work-queue",
            "default",
            "--run-once",
        ],
        expected_code=0,
        expected_output_contains=[
            f"Specified work queue(s) in the work pool {process_work_pool.name!r} are currently paused.",
        ],
    )

    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name=process_work_pool.name,
        work_queues=["default"],
        prefetch_seconds=ANY,
        limit=None,
        heartbeat_interval_seconds=30,
        base_job_template=None,
    )
    mock_worker.return_value.start.assert_awaited_once_with(
        run_once=True, with_healthcheck=False, printer=ANY
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_all_work_queues_paused(mock_worker, process_work_pool):
    invoke_and_assert(
        command=[
            "work-queue",
            "pause",
            "default",
            "--pool",
            process_work_pool.name,
        ],
        expected_code=0,
        expected_output_contains=[
            f"Work queue 'default' in work pool {process_work_pool.name!r} paused"
        ],
    )

    invoke_and_assert(
        command=["worker", "start", "-p", process_work_pool.name, "--run-once"],
        expected_code=0,
        expected_output_contains=[
            f"All work queues in the work pool {process_work_pool.name!r} are currently paused.",
        ],
    )

    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name=process_work_pool.name,
        work_queues=None,
        prefetch_seconds=ANY,
        limit=None,
        heartbeat_interval_seconds=30,
        base_job_template=None,
    )
    mock_worker.return_value.start.assert_awaited_once_with(
        run_once=True, with_healthcheck=False, printer=ANY
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_prefetch_seconds(mock_worker):
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
        work_queues=None,
        prefetch_seconds=30,
        limit=None,
        heartbeat_interval_seconds=30,
        base_job_template=None,
    )
    mock_worker.return_value.start.assert_awaited_once_with(
        run_once=True, with_healthcheck=False, printer=ANY
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_prefetch_seconds_from_setting_by_default(mock_worker):
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
        work_queues=None,
        prefetch_seconds=100,
        limit=None,
        heartbeat_interval_seconds=30,
        base_job_template=None,
    )
    mock_worker.return_value.start.assert_awaited_once_with(
        run_once=True, with_healthcheck=False, printer=ANY
    )


@pytest.mark.usefixtures("use_hosted_api_server")
def test_start_worker_with_limit(mock_worker):
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
        work_queues=None,
        prefetch_seconds=10,
        limit=5,
        heartbeat_interval_seconds=30,
        base_job_template=None,
    )
    mock_worker.return_value.start.assert_awaited_once_with(
        run_once=True, with_healthcheck=False, printer=ANY
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
                f"Discovered type {process_work_pool.type!r} for work pool"
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
async def test_worker_start_fails_informatively_with_bad_type(
    process_work_pool, prefect_client: PrefectClient
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "worker",
            "start",
            "-p",
            process_work_pool.name,
            "-t",
            "not-a-real-type",
        ],
        expected_code=1,
        expected_output_contains=[
            "Could not find a package for worker type",
            "Unable to start worker. Please ensure you have the necessary"
            " dependencies installed to run your desired worker type.",
        ],
    )


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_worker_does_not_run_with_push_pool(push_work_pool):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=[
            "worker",
            "start",
            "--run-once",
            "-p",
            push_work_pool.name,
        ],
        expected_code=1,
        expected_output_contains=[
            (
                f"Discovered type {push_work_pool.type!r} for work pool"
                f" {push_work_pool.name!r}."
            ),
            (
                "Workers are not required for push work pools. "
                "See https://docs.prefect.io/latest/deploy/infrastructure-examples/serverless "
                "for more details."
            ),
        ],
    )


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


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_worker_reports_heartbeat_interval(
    prefect_client: PrefectClient, process_work_pool
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
            "Worker 'test-worker' started!",
            "Worker 'test-worker' stopped!",
        ],
    )

    workers = await prefect_client.read_workers_for_work_pool(
        work_pool_name=process_work_pool.name
    )
    assert len(workers) == 1
    assert workers[0].name == "test-worker"
    assert workers[0].heartbeat_interval_seconds == 30


@pytest.mark.usefixtures("use_hosted_api_server")
class TestInstallPolicyOption:
    async def test_install_policy_if_not_present(
        self, kubernetes_work_pool, monkeypatch
    ):
        run_process_mock = AsyncMock()
        lookup_type_mock = MagicMock()
        lookup_type_mock.side_effect = [KeyError, MockKubernetesWorker]
        monkeypatch.setattr("prefect.cli.worker.run_process", run_process_mock)
        monkeypatch.setattr("prefect.cli.worker.lookup_type", lookup_type_mock)
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "worker",
                "start",
                "--run-once",
                "-p",
                kubernetes_work_pool.name,
                "-n",
                "test-worker",
                "--install-policy=if-not-present",
            ],
            expected_output_contains=[
                "Installing prefect-kubernetes...",
                "Worker 'test-worker' started!",
                "Worker 'test-worker' stopped!",
            ],
        )

        run_process_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "prefect[kubernetes]"],
            stream_output=True,
        )

    @pytest.mark.usefixtures("interactive_console")
    async def test_install_policy_prompt(self, kubernetes_work_pool, monkeypatch):
        run_process_mock = AsyncMock()
        lookup_type_mock = MagicMock()
        lookup_type_mock.side_effect = [KeyError, MockKubernetesWorker]
        monkeypatch.setattr("prefect.cli.worker.run_process", run_process_mock)
        monkeypatch.setattr("prefect.cli.worker.lookup_type", lookup_type_mock)
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "worker",
                "start",
                "--run-once",
                "-p",
                kubernetes_work_pool.name,
                "-n",
                "test-worker",
            ],
            user_input=readchar.key.ENTER,
            expected_output_contains=[
                "Could not find the Prefect integration library for the",
                "kubernetes",
                "Install the library now?",
                "Installing prefect-kubernetes...",
                "Worker 'test-worker' started!",
                "Worker 'test-worker' stopped!",
            ],
        )

        run_process_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "prefect[kubernetes]"],
            stream_output=True,
        )

    @pytest.mark.usefixtures("interactive_console")
    async def test_install_policy_prompt_decline(self, monkeypatch, prefect_client):
        run_process_mock = AsyncMock()
        lookup_type_mock = MagicMock()
        lookup_type_mock.side_effect = [KeyError, MockKubernetesWorker]
        monkeypatch.setattr("prefect.cli.worker.run_process", run_process_mock)
        monkeypatch.setattr("prefect.cli.worker.lookup_type", lookup_type_mock)
        kubernetes_work_pool = await prefect_client.create_work_pool(
            work_pool=WorkPoolCreate(name="test-k8s-work-pool", type="kubernetes")
        )

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "worker",
                "start",
                "--run-once",
                "-p",
                kubernetes_work_pool.name,
                "-n",
                "test-worker",
            ],
            expected_code=1,
            user_input="n" + readchar.key.ENTER,
            expected_output_contains=[
                "Unable to start worker. Please ensure you have the necessary"
                " dependencies installed to run your desired worker type."
            ],
        )

        run_process_mock.assert_not_called()

    @pytest.mark.usefixtures("interactive_console")
    async def test_install_policy_if_not_present_overrides_prompt(
        self, kubernetes_work_pool, monkeypatch
    ):
        run_process_mock = AsyncMock()
        lookup_type_mock = MagicMock()
        lookup_type_mock.side_effect = [KeyError, MockKubernetesWorker]
        monkeypatch.setattr("prefect.cli.worker.run_process", run_process_mock)
        monkeypatch.setattr("prefect.cli.worker.lookup_type", lookup_type_mock)
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "worker",
                "start",
                "--run-once",
                "-p",
                kubernetes_work_pool.name,
                "-n",
                "test-worker",
                "--install-policy=if-not-present",
            ],
            expected_output_contains=[
                "Installing prefect-kubernetes...",
                "Worker 'test-worker' started!",
                "Worker 'test-worker' stopped!",
            ],
        )

        run_process_mock.assert_called_once_with(
            [sys.executable, "-m", "pip", "install", "prefect[kubernetes]"],
            stream_output=True,
        )

    @pytest.mark.usefixtures("interactive_console")
    async def test_install_policy_always(self, kubernetes_work_pool, monkeypatch):
        run_process_mock = AsyncMock()
        lookup_type_mock = MagicMock()
        lookup_type_mock.return_value = MockKubernetesWorker
        monkeypatch.setattr("prefect.cli.worker.run_process", run_process_mock)
        monkeypatch.setattr("prefect.cli.worker.lookup_type", lookup_type_mock)
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "worker",
                "start",
                "--run-once",
                "-p",
                kubernetes_work_pool.name,
                "-n",
                "test-worker",
                "--install-policy=always",
            ],
            expected_output_contains=[
                "Installing prefect-kubernetes...",
                "Worker 'test-worker' started!",
                "Worker 'test-worker' stopped!",
            ],
        )

        run_process_mock.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "prefect[kubernetes]",
                "--upgrade",
            ],
            stream_output=True,
        )

    @pytest.mark.usefixtures("interactive_console")
    async def test_install_policy_never(self, monkeypatch, prefect_client):
        kubernetes_work_pool = await prefect_client.create_work_pool(
            work_pool=WorkPoolCreate(name="test-k8s-work-pool", type="kubernetes")
        )

        run_process_mock = AsyncMock()
        lookup_type_mock = MagicMock()
        lookup_type_mock.side_effect = KeyError
        monkeypatch.setattr("prefect.cli.worker.run_process", run_process_mock)
        monkeypatch.setattr("prefect.cli.worker.lookup_type", lookup_type_mock)
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "worker",
                "start",
                "--run-once",
                "-p",
                kubernetes_work_pool.name,
                "-n",
                "test-worker",
                "--install-policy=never",
            ],
            expected_code=1,
            expected_output_contains=[
                "Unable to start worker. Please ensure you have the necessary"
                " dependencies installed to run your desired worker type."
            ],
        )

        run_process_mock.assert_not_called()

        def test_start_with_prefect_agent_type(worker_type):
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
                    "prefect-agent",
                ],
                expected_code=1,
                expected_output_contains=(
                    "'prefect-agent' typed work pools work with Prefect Agents instead"
                    " of Workers. Please use the 'prefect agent start' to start a"
                    " Prefect Agent."
                ),
            )


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

    settings = get_current_settings()

    # Will connect to the same database as normal test clients
    async with await anyio.open_process(
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
        env={**os.environ, **settings.to_environment_variables()},
    ) as process:
        for _ in range(int(STARTUP_TIMEOUT / POLL_INTERVAL)):
            await anyio.sleep(POLL_INTERVAL)
            assert process.stdout is not None
            received = await TextReceiveStream(process.stdout).receive()
            if "Worker 'test-worker' started!" in received:
                break
        else:
            raise Exception("Worker failed to start")

        assert process.returncode is None, "The worker failed to start up"

        # Yield to the consuming tests
        yield process

        # Then shutdown the process
        try:
            process.terminate()
        except ProcessLookupError:
            pass


class TestWorkerSignalForwarding:
    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM is only used in non-Windows environments",
    )
    async def test_sigint_sends_sigterm(self, worker_process):
        worker_process.send_signal(signal.SIGINT)
        await safe_shutdown(worker_process)

        out = await _receive_stream(worker_process.stdout)

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

        out = await _receive_stream(worker_process.stdout)

        assert "Sending SIGINT" in out, (
            "When sending a SIGTERM, the main process should receive a SIGINT."
            f" Output:\n{out}"
        )

        assert "Worker 'test-worker' stopped!" in out, (
            "When sending a SIGTERM, the main process should shutdown gracefully."
            f" Output:\n{out}"
        )

    async def test_sigint_sends_sigterm_then_sigkill(self, worker_process):
        worker_process.send_signal(signal.SIGINT)
        await anyio.sleep(0.1)  # some time needed for the recursive signal handler
        worker_process.send_signal(signal.SIGINT)
        await safe_shutdown(worker_process)

        out = await TextReceiveStream(worker_process.stdout).receive()

        if sys.platform != "win32":
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
        else:
            assert "Sending CTRL_BREAK_EVENT" in out, (
                "When sending a SIGINT, the main process should send a CTRL_BREAK_EVENT to"
                f" the worker subprocess. Output:\n{out}"
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

        out = await TextReceiveStream(worker_process.stdout).receive()

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
