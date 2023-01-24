import pytest

from prefect.orion.schemas.core import WorkPool
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_WORKERS
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture(autouse=True)
def auto_enable_workers(enable_workers):
    """
    Enable workers for testing
    """
    assert PREFECT_EXPERIMENTAL_ENABLE_WORKERS
    # Import to register worker CLI
    import prefect.experimental.cli.worker  # noqa


class TestCreate:
    async def test_create_work_pool(self, orion_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} -t process",
        )
        assert res.exit_code == 0
        assert f"Created work pool {pool_name}" in res.output
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.name == pool_name
        assert isinstance(client_res, WorkPool)

    # ------ TEMPLATE ------
    async def test_default_template(self, orion_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name}",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.base_job_template == dict()

    # ------ PAUSED ------
    async def test_default_paused(self, orion_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name}",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.is_paused is False

    async def test_paused_true(self, orion_client):
        pool_name = "my-pool"
        res = await run_sync_in_worker_thread(
            invoke_and_assert,
            f"work-pool create {pool_name} --paused",
        )
        assert res.exit_code == 0
        client_res = await orion_client.read_work_pool(pool_name)
        assert client_res.is_paused is True
