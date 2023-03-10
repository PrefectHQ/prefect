from unittest.mock import ANY

import pytest

import prefect
from prefect.client.orchestration import PrefectClient
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import MagicMock
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS
    # Import to register worker CLI
    import prefect.experimental.cli.worker  # noqa


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


async def test_start_worker_creates_work_pool(orion_client: PrefectClient):
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

    work_pool = await orion_client.read_work_pool("not-yet-created-pool")
    assert work_pool is not None
    assert work_pool.name == "not-yet-created-pool"
    assert work_pool.default_queue_id is not None


def test_start_worker_with_work_queue_names(monkeypatch, process_work_pool):
    mock_worker = MagicMock()
    monkeypatch.setattr(
        prefect.experimental.cli.worker, "lookup_type", lambda x, y: mock_worker
    )
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


def test_start_worker_with_prefetch_seconds(monkeypatch):
    mock_worker = MagicMock()
    monkeypatch.setattr(
        prefect.experimental.cli.worker, "lookup_type", lambda x, y: mock_worker
    )
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


def test_start_worker_with_prefetch_seconds_from_setting_by_default(monkeypatch):
    mock_worker = MagicMock()
    monkeypatch.setattr(
        prefect.experimental.cli.worker, "lookup_type", lambda x, y: mock_worker
    )
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


def test_start_worker_with_limit(monkeypatch):
    mock_worker = MagicMock()
    monkeypatch.setattr(
        prefect.experimental.cli.worker, "lookup_type", lambda x, y: mock_worker
    )
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


async def test_worker_joins_existing_pool(work_pool, orion_client: PrefectClient):
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

    workers = await orion_client.read_workers_for_work_pool(
        work_pool_name=work_pool.name
    )
    assert workers[0].name == "test-worker"


async def test_worker_discovers_work_pool_type(
    process_work_pool, orion_client: PrefectClient
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

    workers = await orion_client.read_workers_for_work_pool(
        work_pool_name=process_work_pool.name
    )
    assert workers[0].name == "test-worker"


async def test_worker_errors_if_no_type_and_non_existent_work_pool():
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
        expected_code=1,
        expected_output_contains=[
            "Work pool 'not-here' does not exist. To create a new work pool "
            "on worker startup, include a worker type with the --type option."
        ],
    )
