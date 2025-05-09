import json
import textwrap
from uuid import uuid4

import alembic.script
import pytest
import sqlalchemy as sa

from prefect.server.database.alembic_commands import (
    alembic_config,
    alembic_downgrade,
    alembic_upgrade,
)
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.database.orm_models import (
    AioSqliteORMConfiguration,
    AsyncPostgresORMConfiguration,
)
from prefect.server.models.variables import read_variables
from prefect.server.utilities.database import get_dialect
from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL
from prefect.types._datetime import now
from prefect.utilities.asyncutils import run_sync_in_worker_thread

pytestmark = pytest.mark.service("database")


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


@pytest.mark.timeout(120)
async def test_orion_full_migration_works_with_data_in_db(sample_db_data):
    """
    Tests that downgrade migrations work when the database has data in it.
    """
    try:
        await run_sync_in_worker_thread(alembic_downgrade, revision="base")
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
        pytest.skip(reason="Test is excessively slow on SQLite")
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
                    f" 'RUNNING', 'My Custom Name', '{now('UTC')}');"
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
                    f" 'RUNNING', 'My Custom Name', '{now('UTC')}');"
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
            assert expected_flow_runs == flow_runs, (
                "state_name is backfilled for flow runs"
            )

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
            assert expected_task_runs == task_runs, (
                "state_name is backfilled for task runs"
            )

    finally:
        await run_sync_in_worker_thread(alembic_upgrade)


async def test_backfill_artifacts(db):
    """
    Tests that the backfill_artifacts migration works as expected
    """
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    dialect = get_dialect(connection_url)

    # get the proper migration revisions
    if dialect.name == "postgresql":
        revisions = ("310dda75f561", "15f5083c16bd")
    else:
        revisions = ("3d46e23593d6", "2dbcec43c857")

    # insert some artifacts into the database
    artifacts = [
        {
            "id": uuid4(),
            "key": "foo",
            "data": {"value": 1},
            "description": "Artifact 1",
            "flow_run_id": uuid4(),
            "task_run_id": uuid4(),
            "type": "type1",
        },
        {
            "id": uuid4(),
            "key": "bar",
            "data": {"value": 2},
            "description": "Artifact 2",
            "flow_run_id": uuid4(),
            "task_run_id": uuid4(),
            "type": "type2",
        },
        {
            "id": uuid4(),
            "key": "voltaic",
            "data": {"value": 3},
            "description": "Artifact 3",
            "flow_run_id": uuid4(),
            "task_run_id": uuid4(),
            "type": "type3",
        },
        {
            "id": uuid4(),
            "key": "lotus",
            "data": {"value": 4},
            "description": "Artifact 4",
            "flow_run_id": uuid4(),
            "task_run_id": uuid4(),
            "type": "type4",
        },
        {
            "id": uuid4(),
            "key": "treasure",
            "data": {"value": 5},
            "description": "Artifact 5",
            "flow_run_id": uuid4(),
            "task_run_id": uuid4(),
            "type": "type5",
        },
    ]
    try:
        # downgrade to the previous revision
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])
        session = await db.session()
        async with session:
            for artifact in artifacts:
                await session.execute(
                    sa.text(
                        "INSERT INTO artifact (id, key, data, description,"
                        " flow_run_id, task_run_id, type) VALUES"
                        f" ('{artifact['id']}', '{artifact['key']}',"
                        f" '{json.dumps(artifact['data'])}',"
                        f" '{artifact['description']}', '{artifact['flow_run_id']}',"
                        f" '{artifact['task_run_id']}', '{artifact['type']}')"
                    )
                )
                await session.execute(
                    sa.text(
                        "INSERT INTO artifact_collection (key, id, latest_id) VALUES"
                        f" ('{artifact['key']}', '{uuid4()}', '{artifact['id']}')"
                    )
                )
                await session.commit()

        # run the migration that should backfill the artifact_collection table
        await run_sync_in_worker_thread(alembic_upgrade, revision=revisions[1])

        # check to see if the migration worked
        session = await db.session()
        async with session:
            for artifact in artifacts:
                result = (
                    await session.execute(
                        sa.text(
                            "SELECT flow_run_id, task_run_id, type, description"
                            " FROM artifact_collection WHERE latest_id ="
                            f" '{artifact['id']}'"
                        )
                    )
                ).first()

                result = (
                    str(result[0]),
                    str(result[1]),
                    result[2],
                    result[3],
                )

                expected_result = (
                    str(artifact["flow_run_id"]),
                    str(artifact["task_run_id"]),
                    artifact["type"],
                    artifact["description"],
                )
                assert result == expected_result, (
                    "data migration populates artifact_collection table"
                )

    finally:
        await run_sync_in_worker_thread(alembic_upgrade)


@pytest.mark.timeout(120)
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
                        "SELECT work_queue_id FROM deployment WHERE name ="
                        " 'my-deployment';"
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


async def test_not_adding_default_agent_pool_when_all_work_queues_have_work_pool(db):
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

            # insert some work queues with a work pool into the database
            await session.execute(
                sa.text(
                    "INSERT INTO work_pool (name, type) VALUES ('existing-pool', 'prefect-agent');"
                )
            )
            existing_pool_id = (
                await session.execute(
                    sa.text("SELECT id FROM work_pool WHERE name = 'existing-pool';")
                )
            ).scalar()

            await session.execute(
                sa.text(
                    "INSERT INTO work_queue (name, work_pool_id) VALUES ('queue-1', :existing_pool_id);"
                ),
                {"existing_pool_id": existing_pool_id},
            )
            await session.execute(
                sa.text(
                    "INSERT INTO work_queue (name, work_pool_id) VALUES ('queue-2', :existing_pool_id);"
                ),
                {"existing_pool_id": existing_pool_id},
            )
            await session.execute(
                sa.text(
                    "INSERT INTO work_queue (name, work_pool_id) VALUES ('queue-3', :existing_pool_id);"
                ),
                {"existing_pool_id": existing_pool_id},
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
            # Check that the default-agent-pool is not created
            default_pool_exists = (
                await session.execute(
                    sa.text(
                        "SELECT COUNT(*) FROM work_pool WHERE name = 'default-agent-pool';"
                    )
                )
            ).scalar()

            assert default_pool_exists == 0

            # Check that the existing work queues are not modified
            work_queue_names = (
                await session.execute(sa.text("SELECT name FROM work_queue;"))
            ).fetchall()

            assert len(work_queue_names) == 3
            assert set(work_queue_names) == set(pre_work_queue_names)

    finally:
        await run_sync_in_worker_thread(alembic_upgrade)


async def test_migrate_variables_to_json(db):
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    dialect = get_dialect(connection_url)

    # get the proper migration revisions
    if dialect.name == "postgresql":
        revisions = ("b23c83a12cb4", "94622c1663e8")
    else:
        revisions = ("20fbd53b3cef", "2ac65f1758c2")

    session = await db.session()

    try:
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])

        async with session:
            # clear the variables table
            await session.execute(sa.text("DELETE FROM variable;"))

            await session.execute(
                sa.text(
                    """INSERT INTO variable (name, value) VALUES ('var1', 'value1'), ('var2', '"value2"'), ('var3', '\"value3\"')"""
                )
            )

            await session.commit()

            variable_values = (
                await session.execute(sa.text("SELECT value FROM variable;"))
            ).fetchall()

            values = {value[0] for value in variable_values}
            assert values == {"value1", '"value2"', '"value3"'}

        # run the upgrade
        await run_sync_in_worker_thread(alembic_upgrade, revision=revisions[1])

        # string values should be able to be read as json
        # but parsed as strings on read from the models layer
        async with session:
            variables = await read_variables(session)
            values = {variable.value for variable in variables}
            assert values == {"value1", '"value2"', '"value3"'}

        # reverse the migration
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])

        # original string values should be present
        async with session:
            variable_values = (
                await session.execute(sa.text("SELECT value FROM variable;"))
            ).fetchall()

            values = {value[0] for value in variable_values}
            assert values == {"value1", '"value2"', '"value3"'}

    finally:
        async with session:
            await session.execute(sa.text("DELETE FROM variable;"))
            await session.commit()
        await run_sync_in_worker_thread(alembic_upgrade)


async def test_migrate_flow_run_notifications_to_automations(db: PrefectDBInterface):
    connection_url = PREFECT_API_DATABASE_CONNECTION_URL.value()
    dialect = get_dialect(connection_url)

    # get the proper migration revisions
    if dialect.name == "postgresql":
        revisions = ("7a73514ca2d6", "4160a4841eed")
    else:
        revisions = ("bbca16f6f218", "7655f31c5157")

    session = await db.session()

    try:
        await run_sync_in_worker_thread(alembic_downgrade, revision=revisions[0])

        async with session:
            # clear the flow_run_notification_policy table
            await session.execute(sa.text("DELETE FROM flow_run_notification_policy;"))
            # clear the automation table
            await session.execute(sa.text("DELETE FROM automation;"))
            await session.commit()

            # insert a block type and get the id
            await session.execute(
                sa.text(
                    "INSERT INTO block_type (name, slug) VALUES ('Test Block Type', 'test-block-type');"
                )
            )
            block_type_id = (
                await session.execute(
                    sa.text("SELECT id FROM block_type WHERE slug = 'test-block-type';")
                )
            ).scalar()

            # insert a block schema and get the id
            await session.execute(
                sa.text(
                    "INSERT INTO block_schema (block_type_id, checksum) VALUES (:block_type_id, 'test-checksum');"
                ),
                {"block_type_id": block_type_id},
            )
            block_schema_id = (
                await session.execute(
                    sa.text(
                        "SELECT id FROM block_schema WHERE checksum = 'test-checksum';"
                    )
                )
            ).scalar()

            # insert a block document and get the id
            await session.execute(
                sa.text(
                    "INSERT INTO block_document (name, block_schema_id, block_type_id) VALUES ('test-block-document', :block_schema_id, :block_type_id);"
                ),
                {"block_schema_id": block_schema_id, "block_type_id": block_type_id},
            )
            block_document_id = (
                await session.execute(
                    sa.text(
                        "SELECT id FROM block_document WHERE name = 'test-block-document';"
                    )
                )
            ).scalar()

            # insert a flow run notification policy
            await session.execute(
                sa.text(
                    "INSERT INTO flow_run_notification_policy (is_active, state_names, tags, message_template, block_document_id) VALUES (TRUE, '[]', '[]', null, :block_document_id);"
                ),
                {"block_document_id": block_document_id},
            )

            # insert a flow run notification policy
            await session.execute(
                sa.text(
                    "INSERT INTO flow_run_notification_policy (is_active, state_names, tags, message_template, block_document_id) VALUES (FALSE, '[\"Running\"]', '[\"tag1\", \"tag2\"]', 'Flow {flow_name} is in state {flow_run_state_name}', :block_document_id);"
                ),
                {"block_document_id": block_document_id},
            )

            await session.commit()

        # run the migration
        await run_sync_in_worker_thread(alembic_upgrade, revision=revisions[1])

        async with session:
            # verify two automations were created
            automations = (
                await session.execute(
                    sa.text(
                        "SELECT name, description, enabled, trigger, actions FROM automation;"
                    )
                )
            ).fetchall()
            assert len(automations) == 2

            enabled_automation = next(
                automation for automation in automations if automation[2]
            )
            disabled_automation = next(
                automation for automation in automations if not automation[2]
            )

            # check the name
            assert enabled_automation[0] == "Flow Run State Change Notification"
            assert disabled_automation[0] == "Flow Run State Change Notification"

            # check the description
            assert (
                enabled_automation[1] == "Migrated from a flow run notification policy"
            )
            assert (
                disabled_automation[1] == "Migrated from a flow run notification policy"
            )

            # check the trigger
            enabled_trigger = (
                json.loads(enabled_automation[3])
                if dialect.name == "sqlite"
                else enabled_automation[3]
            )
            enabled_trigger_id = enabled_trigger["id"]
            assert enabled_trigger == {
                "id": enabled_trigger_id,
                "type": "event",
                "after": [],
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.*"],
                "within": 10,
                "posture": "Reactive",
                "for_each": ["prefect.resource.id"],
                "threshold": 1,
                "match_related": {},
            }
            disabled_trigger = (
                json.loads(disabled_automation[3])
                if dialect.name == "sqlite"
                else disabled_automation[3]
            )
            disabled_trigger_id = disabled_trigger["id"]
            assert disabled_trigger == {
                "id": disabled_trigger_id,
                "type": "event",
                "after": [],
                "match": {"prefect.resource.id": "prefect.flow-run.*"},
                "expect": ["prefect.flow-run.Running"],
                "within": 10,
                "posture": "Reactive",
                "for_each": ["prefect.resource.id"],
                "threshold": 1,
                "match_related": {
                    "prefect.resource.id": ["prefect.tag.tag1", "prefect.tag.tag2"],
                    "prefect.resource.role": "tag",
                },
            }
            # check the actions

            enabled_actions = (
                json.loads(enabled_automation[4])
                if dialect.name == "sqlite"
                else enabled_automation[4]
            )
            disabled_actions = (
                json.loads(disabled_automation[4])
                if dialect.name == "sqlite"
                else disabled_automation[4]
            )
            assert enabled_actions == [
                {
                    "body": textwrap.dedent("""
                        Flow run {{ flow.name }}/{{ flow_run.name }} observed in state `{{ flow_run.state.name }}` at {{ flow_run.state.timestamp }}.
                        Flow ID: {{ flow_run.flow_id }}
                        Flow run ID: {{ flow_run.id }}
                        Flow run URL: {{ flow_run|ui_url }}
                        State message: {{ flow_run.state.message }}
                        """),
                    "type": "send-notification",
                    "subject": "Prefect flow run notification",
                    "block_document_id": str(block_document_id),
                }
            ]
            assert disabled_actions == [
                {
                    "body": "Flow {{ flow.name }} is in state {{ flow_run.state.name }}",
                    "type": "send-notification",
                    "subject": "Prefect flow run notification",
                    "block_document_id": str(block_document_id),
                }
            ]
    finally:
        await run_sync_in_worker_thread(alembic_upgrade)
