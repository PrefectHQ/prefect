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
        command=["worker", "start", "--run-once", "-p", "not-yet-created-pool"],
        expected_code=0,
        expected_output_contains=["Worker", "stopped!", "Worker", "started!"],
    )

    work_pool = await orion_client.read_work_pool("not-yet-created-pool")
    assert work_pool is not None
    assert work_pool.name == "not-yet-created-pool"
    assert work_pool.default_queue_id is not None


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
        ],
        expected_code=0,
    )
    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name="test",
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
            ],
            expected_code=0,
        )
    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name="test",
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
        ],
        expected_code=0,
    )
    mock_worker.assert_called_once_with(
        name=None,
        work_pool_name="test",
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
