"""Backfill state_name

Revision ID: 14dc68cc5853
Revises: 605ebb4e9155
Create Date: 2022-04-21 09:55:19.820177

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "14dc68cc5853"
down_revision = "605ebb4e9155"
branch_labels = None
depends_on = None


def upgrade():
    """
    Backfills state_name column for task_run and flow_run tables.

    This is a data only migration that can be run as many
    times as desired.
    """

    update_flow_run_state_name_in_batches = """
        WITH null_flow_run_state_name_cte as (SELECT id from flow_run where state_name is null and state_id is not null limit 500)
        UPDATE flow_run
        SET state_name = flow_run_state.name
        FROM flow_run_state, null_flow_run_state_name_cte
        WHERE flow_run.state_id = flow_run_state.id
        AND flow_run.id = null_flow_run_state_name_cte.id;
    """

    update_task_run_state_name_in_batches = """
        WITH null_task_run_state_name_cte as (SELECT id from task_run where state_name is null and state_id is not null limit 500)
        UPDATE task_run
        SET state_name = task_run_state.name
        FROM task_run_state, null_task_run_state_name_cte
        WHERE task_run.state_id = task_run_state.id
        AND task_run.id = null_task_run_state_name_cte.id;
    """

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        while True:
            # execute until we've backfilled all flow run state names
            # autocommit mode will commit each time `execute` is called
            result = conn.execute(sa.text(update_flow_run_state_name_in_batches))
            if result.rowcount <= 0:
                break

        while True:
            # execute until we've backfilled all task run state names
            # autocommit mode will commit each time `execute` is called
            result = conn.execute(sa.text(update_task_run_state_name_in_batches))
            if result.rowcount <= 0:
                break


def downgrade():
    """
    Data only migration. No action on downgrade.
    """
