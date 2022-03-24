import alembic.script
import pytest

from prefect.orion.database.alembic_commands import (
    alembic_config,
    alembic_downgrade,
    alembic_upgrade,
)
from prefect.orion.database.orm_models import (
    AioSqliteORMConfiguration,
    AsyncPostgresORMConfiguration,
)
from prefect.utilities.asyncio import run_sync_in_worker_thread


@pytest.fixture
async def sample_db_data(
    flow,
    flow_run,
    flow_run_state,
    task_run,
    task_run_state,
    deployment,
    block,
    block_spec,
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


@pytest.mark.parametrize(
    "orm_config", [AioSqliteORMConfiguration, AsyncPostgresORMConfiguration]
)
def test_only_single_head_revision_in_migrations(orm_config):
    config = alembic_config()
    script = alembic.script.ScriptDirectory.from_config(config)

    script.version_locations = [orm_config().versions_dir]

    # This will raise if there are multiple heads
    head = script.get_current_head()

    assert head is not None, "Head revision is missing"
