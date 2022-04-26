from uuid import uuid4

import alembic.script
import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion.database.alembic_commands import (
    alembic_config,
    alembic_downgrade,
    alembic_upgrade,
)
from prefect.orion.database.orm_models import (
    AioSqliteORMConfiguration,
    AsyncPostgresORMConfiguration,
)
from prefect.orion.utilities.database import get_dialect
from prefect.settings import PREFECT_ORION_DATABASE_CONNECTION_URL
from prefect.utilities.asyncio import run_sync_in_worker_thread


@pytest.fixture
async def sample_db_data(
    flow,
    flow_run,
    flow_run_state,
    task_run,
    task_run_state,
    deployment,
    block_document,
    block_schema,
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


async def test_backfill_state_name(db, flow):
    """
    Tests state_name is backfilled correctly for the flow_run
    and task_run tables by a specific migration
    """
    connection_url = PREFECT_ORION_DATABASE_CONNECTION_URL.value()
    dialect = get_dialect(connection_url)

    # get the proper migration revisions
    if dialect.name == "postgresql":
        revisions = ("605ebb4e9155", "14dc68cc5853")
    else:
        revisions = ("7f5f335cace3", "db6bde582447")

    flow_run_id = uuid4()
    null_state_flow_run_id = uuid4()
    flow_run_state_1_id = uuid4()
    flow_run_state_2_id = uuid4()

    task_run_id = uuid4()
    null_state_task_run_id = uuid4()
    task_run_state_1_id = uuid4()
    task_run_state_2_id = uuid4()
    try:
        # downgrade to the previous revision
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])
        session = await db.session()
        async with session:
            # insert some flow and task runs into the database, using raw SQL to avoid
            # future orm incompatibilities
            await session.execute(
                sa.text(
                    f"INSERT INTO flow_run (id, name, flow_id) values ('{flow_run_id}', 'foo', '{flow.id}');"
                )
            )
            await session.execute(
                sa.text(
                    f"INSERT INTO flow_run (id, name, flow_id) values ('{null_state_flow_run_id}', 'null state', '{flow.id}');"
                )
            )
            await session.execute(
                sa.text(
                    f"INSERT INTO flow_run_state (id, flow_run_id, type, name) values ('{flow_run_state_1_id}', '{flow_run_id}', 'SCHEDULED', 'Scheduled');"
                )
            )
            await session.execute(
                sa.text(
                    f"INSERT INTO flow_run_state (id, flow_run_id, type, name, timestamp) values ('{flow_run_state_2_id}', '{flow_run_id}', 'RUNNING', 'My Custom Name', '{pendulum.now('UTC')}');"
                )
            )
            await session.execute(
                sa.text(
                    f"UPDATE flow_run SET state_id = '{flow_run_state_2_id}' WHERE id = '{flow_run_id}'"
                )
            )

            await session.execute(
                sa.text(
                    f"INSERT INTO task_run (id, name, task_key, dynamic_key, flow_run_id) values ('{task_run_id}', 'foo-task', 'foo-task', 0, '{flow_run_id}');"
                )
            )
            await session.execute(
                sa.text(
                    f"INSERT INTO task_run (id, name, task_key, dynamic_key, flow_run_id) values ('{null_state_task_run_id}', 'null-state-task', 'null-state-task', 0, '{flow_run_id}');"
                )
            )
            await session.execute(
                sa.text(
                    f"INSERT INTO task_run_state (id, task_run_id, type, name) values ('{task_run_state_1_id}', '{task_run_id}', 'SCHEDULED', 'Scheduled');"
                )
            )
            await session.execute(
                sa.text(
                    f"INSERT INTO task_run_state (id, task_run_id, type, name, timestamp) values ('{task_run_state_2_id}', '{task_run_id}', 'RUNNING', 'My Custom Name', '{pendulum.now('UTC')}');"
                )
            )
            await session.execute(
                sa.text(
                    f"UPDATE task_run SET state_id = '{task_run_state_2_id}' WHERE id = '{task_run_id}'"
                )
            )
            await session.commit()

        # run the migration that should backfill the state_name column
        await run_sync_in_worker_thread(alembic_upgrade, revision=revisions[1])

        # check to see the revision worked
        session = await db.session()
        async with session:
            flow_runs = [
                (str(fr[0]), fr[1], fr[2])
                for fr in (
                    await session.execute(
                        sa.text(
                            "SELECT id, name, state_name FROM flow_run order by name"
                        )
                    )
                ).all()
            ]
            expected_flow_runs = [
                (str(flow_run_id), "foo", "My Custom Name"),
                (str(null_state_flow_run_id), "null state", None),
            ]
            assert (
                expected_flow_runs == flow_runs
            ), "state_name is backfilled for flow runs"

            task_runs = [
                (str(tr[0]), tr[1], tr[2])
                for tr in (
                    await session.execute(
                        sa.text(
                            "SELECT id, name, state_name FROM task_run order by name"
                        )
                    )
                ).all()
            ]
            expected_task_runs = [
                (str(task_run_id), "foo-task", "My Custom Name"),
                (str(null_state_task_run_id), "null-state-task", None),
            ]
            assert (
                expected_task_runs == task_runs
            ), "state_name is backfilled for task runs"

    finally:
        await run_sync_in_worker_thread(alembic_upgrade)
