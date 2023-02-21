from uuid import uuid4

import alembic.script
import pendulum
import pytest
import sqlalchemy as sa

from prefect.server.database.alembic_commands import (
    alembic_config,
    alembic_downgrade,
    alembic_upgrade,
)
from prefect.server.database.orm_models import (
    AioSqliteORMConfiguration,
    AsyncPostgresORMConfiguration,
)
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture
async def sample_db_data(
    flow,
    flow_run,
    flow_run_state,
    task_run,
    task_run_state,
    deployment,
    block_document,
):
    """Adds sample data to the database for testing migrations"""


@pytest.mark.flaky(max_runs=3)
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
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
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
                    f"INSERT INTO flow_run (id, name, flow_id) values ('{flow_run_id}',"
                    f" 'foo', '{flow.id}');"
                )
            )
            await session.execute(
                sa.text(
                    "INSERT INTO flow_run (id, name, flow_id) values"
                    f" ('{null_state_flow_run_id}', 'null state', '{flow.id}');"
                )
            )
            await session.execute(
                sa.text(
                    "INSERT INTO flow_run_state (id, flow_run_id, type, name) values"
                    f" ('{flow_run_state_1_id}', '{flow_run_id}', 'SCHEDULED',"
                    " 'Scheduled');"
                )
            )
            await session.execute(
                sa.text(
                    "INSERT INTO flow_run_state (id, flow_run_id, type, name,"
                    f" timestamp) values ('{flow_run_state_2_id}', '{flow_run_id}',"
                    f" 'RUNNING', 'My Custom Name', '{pendulum.now('UTC')}');"
                )
            )
            await session.execute(
                sa.text(
                    f"UPDATE flow_run SET state_id = '{flow_run_state_2_id}' WHERE id ="
                    f" '{flow_run_id}'"
                )
            )

            await session.execute(
                sa.text(
                    "INSERT INTO task_run (id, name, task_key, dynamic_key,"
                    f" flow_run_id) values ('{task_run_id}', 'foo-task', 'foo-task', 0,"
                    f" '{flow_run_id}');"
                )
            )
            await session.execute(
                sa.text(
                    "INSERT INTO task_run (id, name, task_key, dynamic_key,"
                    f" flow_run_id) values ('{null_state_task_run_id}',"
                    f" 'null-state-task', 'null-state-task', 0, '{flow_run_id}');"
                )
            )
            await session.execute(
                sa.text(
                    "INSERT INTO task_run_state (id, task_run_id, type, name) values"
                    f" ('{task_run_state_1_id}', '{task_run_id}', 'SCHEDULED',"
                    " 'Scheduled');"
                )
            )
            await session.execute(
                sa.text(
                    "INSERT INTO task_run_state (id, task_run_id, type, name,"
                    f" timestamp) values ('{task_run_state_2_id}', '{task_run_id}',"
                    f" 'RUNNING', 'My Custom Name', '{pendulum.now('UTC')}');"
                )
            )
            await session.execute(
                sa.text(
                    f"UPDATE task_run SET state_id = '{task_run_state_2_id}' WHERE id ="
                    f" '{task_run_id}'"
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


async def test_adding_work_pool_tables_does_not_remove_fks(db, flow):
    """
    Tests state_name is backfilled correctly for the flow_run
    and task_run tables by a specific migration
    """
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    dialect = get_dialect(connection_url)

    # get the proper migration revisions
    if dialect.name == "postgresql":
        # Not relevant for Postgres
        return
    else:
        revisions = ("7201de756d85", "fe77ad0dda06")

    flow_run_id = uuid4()
    flow_run_state_1_id = uuid4()

    try:
        # downgrade to the previous revision
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])
        session = await db.session()
        async with session:
            # insert some flow and task runs into the database, using raw SQL to avoid
            # future orm incompatibilities
            await session.execute(
                sa.text(
                    f"INSERT INTO flow_run (id, name, flow_id) values ('{flow_run_id}',"
                    f" 'foo', '{flow.id}');"
                )
            )

            await session.execute(
                sa.text(
                    "INSERT INTO flow_run_state (id, flow_run_id, type, name) values"
                    f" ('{flow_run_state_1_id}', '{flow_run_id}', 'SCHEDULED',"
                    " 'Scheduled');"
                )
            )
            await session.execute(
                sa.text(
                    f"UPDATE flow_run SET state_id = '{flow_run_state_1_id}' WHERE id ="
                    f" '{flow_run_id}'"
                )
            )

            await session.commit()

        async with session:
            # Confirm the state_id is populated
            pre_migration_flow_run_state_id = (
                await session.execute(
                    sa.text(f"SELECT state_id FROM flow_run WHERE id = '{flow_run_id}'")
                )
            ).scalar()

            assert pre_migration_flow_run_state_id == str(flow_run_state_1_id)

        # run the migration
        await run_sync_in_worker_thread(alembic_upgrade, revision=revisions[1])

        # check to see the revision did not remove state ids
        session = await db.session()
        async with session:
            # Flow runs should still have their state ids
            post_migration_flow_run_state_id = (
                await session.execute(
                    sa.text(f"SELECT state_id FROM flow_run WHERE id = '{flow_run_id}'")
                )
            ).scalar()

            assert post_migration_flow_run_state_id == str(flow_run_state_1_id)

    finally:
        await run_sync_in_worker_thread(alembic_upgrade)


async def test_adding_default_agent_pool_with_existing_default_queue_migration(
    db, flow
):
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    dialect = get_dialect(connection_url)

    # get the proper migration revisions
    if dialect.name == "postgresql":
        revisions = ("0a1250a5aa25", "f98ae6d8e2cc")
    else:
        revisions = ("b9bda9f142f1", "1678f2fb8b33")

    try:
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])

        session = await db.session()
        async with session:
            # clear the work queue table
            await session.execute(sa.text("DELETE FROM work_queue;"))
            await session.commit()

            # insert some work queues into the database
            await session.execute(
                sa.text("INSERT INTO work_queue (name) values ('default');")
            )
            await session.execute(
                sa.text("INSERT INTO work_queue (name) values ('queue-1');")
            )
            await session.execute(
                sa.text("INSERT INTO work_queue (name) values ('queue-2');")
            )
            await session.commit()

            # Insert a flow run and deployment to check if they are correctly assigned a work queue ID
            flow_run_id = uuid4()
            await session.execute(
                sa.text(
                    "INSERT INTO flow_run (id, name, flow_id, work_queue_name) values"
                    f" ('{flow_run_id}', 'foo', '{flow.id}', 'queue-1');"
                )
            )
            await session.execute(
                sa.text(
                    "INSERT INTO deployment (name, flow_id, work_queue_name) values"
                    f" ('my-deployment', '{flow.id}', 'queue-1');"
                )
            )
            await session.commit()

        async with session:
            # Confirm the work queues are present
            pre_work_queue_ids = (
                await session.execute(sa.text("SELECT id FROM work_queue;"))
            ).fetchall()

            assert len(pre_work_queue_ids) == 3

        # run the migration
        await run_sync_in_worker_thread(alembic_upgrade, revision=revisions[1])

        session = await db.session()
        async with session:
            # Check that work queues are assigned to the default agent pool
            default_pool_id = (
                await session.execute(
                    sa.text(
                        "SELECT id FROM work_pool WHERE name = 'default-agent-pool';"
                    )
                )
            ).scalar()

            work_queue_ids = (
                await session.execute(
                    sa.text(
                        "SELECT id FROM work_queue WHERE work_pool_id ="
                        f" '{default_pool_id}';"
                    )
                )
            ).fetchall()

            assert len(work_queue_ids) == 3
            assert set(work_queue_ids) == set(pre_work_queue_ids)

            # Check that the flow run and deployment are assigned to the correct work queue
            queue_1 = (
                await session.execute(
                    sa.text("SELECT id FROM work_queue WHERE name = 'queue-1';")
                )
            ).fetchone()
            flow_run = (
                await session.execute(
                    sa.text(
                        "SELECT work_queue_id FROM flow_run WHERE id ="
                        f" '{flow_run_id}';"
                    )
                )
            ).fetchone()
            deployment = (
                await session.execute(
                    sa.text(
                        f"SELECT work_queue_id FROM deployment WHERE name ="
                        f" 'my-deployment';"
                    )
                )
            ).fetchone()

            assert queue_1[0] == flow_run[0]
            assert queue_1[0] == deployment[0]

    finally:
        await run_sync_in_worker_thread(alembic_upgrade)


async def test_adding_default_agent_pool_without_existing_default_queue_migration(db):
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    dialect = get_dialect(connection_url)

    # get the proper migration revisions
    if dialect.name == "postgresql":
        revisions = ("0a1250a5aa25", "f98ae6d8e2cc")
    else:
        revisions = ("b9bda9f142f1", "1678f2fb8b33")

    try:
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])

        session = await db.session()
        async with session:
            # clear the work queue table
            await session.execute(sa.text("DELETE FROM work_queue;"))
            await session.commit()

            # insert some work queues into the database
            await session.execute(
                sa.text("INSERT INTO work_queue (name) values ('queue-1');")
            )
            await session.execute(
                sa.text("INSERT INTO work_queue (name) values ('queue-2');")
            )
            await session.execute(
                sa.text("INSERT INTO work_queue (name) values ('queue-3');")
            )
            await session.commit()

        async with session:
            # Confirm the work queues are present
            pre_work_queue_names = (
                await session.execute(sa.text("SELECT name FROM work_queue;"))
            ).fetchall()

            assert len(pre_work_queue_names) == 3

        # run the migration
        await run_sync_in_worker_thread(alembic_upgrade, revision=revisions[1])

        session = await db.session()
        async with session:
            # Check that work queues are assigned to the default agent pool
            default_pool_id = (
                await session.execute(
                    sa.text(
                        "SELECT id FROM work_pool WHERE name = 'default-agent-pool';"
                    )
                )
            ).scalar()

            work_queue_names = (
                await session.execute(
                    sa.text(
                        "SELECT name FROM work_queue WHERE work_pool_id ="
                        f" '{default_pool_id}';"
                    )
                )
            ).fetchall()

            assert len(work_queue_names) == 4
            assert set(work_queue_names) == set(pre_work_queue_names).union(
                [("default",)]
            )

    finally:
        await run_sync_in_worker_thread(alembic_upgrade)
