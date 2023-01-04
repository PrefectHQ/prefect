from pathlib import Path

import pytest

from prefect.experimental.workers.base import BaseWorker
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_WORKERS


class WorkerTestImpl(BaseWorker):
    type = "test"

    def run(self):
        pass

    def verify_submitted_deployment(self):
        pass


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS


async def test_worker_raises_if_started_outside_of_context_manager():
    with pytest.raises(RuntimeError, match="Worker has not been setup."):
        await WorkerTestImpl(name="test", worker_pool_name="test-worker-pool").start()


async def test_worker_creates_workflows_directory_during_setup(tmp_path: Path):
    await WorkerTestImpl(
        name="test",
        worker_pool_name="test-worker-pool",
        workflow_storage_path=tmp_path / "workflows",
    ).setup()
    assert (tmp_path / "workflows").exists()
