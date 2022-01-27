import pytest

from prefect.orion.database.alembic_commands import alembic_upgrade, alembic_downgrade
from prefect.utilities.asyncio import run_sync_in_worker_thread


@pytest.fixture
async def sample_db_data(
    flow,
    flow_run,
    flow_run_state,
    task_run
):
    """Adds sample data to the database for testing migrations"""


async def test_orion_full_migration_works_with_data_in_db(sample_db_data):
    """
    Tests that downgrade migrations work when the database has data in it.
    """
    try:
        await run_sync_in_worker_thread(alembic_downgrade)
    finally:
        await run_sync_in_worker_thread(alembic_upgrade)
