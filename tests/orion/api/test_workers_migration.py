import pytest

from prefect.settings import PREFECT_BETA_WORKERS_ENABLED


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_BETA_WORKERS_ENABLED


# class TestWorkQueueMigration:
#     async def test_worker_pool_created
