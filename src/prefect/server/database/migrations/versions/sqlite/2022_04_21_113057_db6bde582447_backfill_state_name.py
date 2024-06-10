"""Backfill state_name

Revision ID: db6bde582447
Revises: 7f5f335cace3
Create Date: 2022-04-21 11:30:57.542292

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "db6bde582447"
down_revision = "7f5f335cace3"
branch_labels = None
depends_on = None


def upgrade():
    """
    Backfills state_name column for task_run and flow_run tables.

    This is a data only migration that can be run as many
    times as desired.
    """

    update_flow_run_state_name_in_batches = """
        UPDATE flow_run
        SET state_name = (SELECT name from flow_run_state where flow_run.state_id = flow_run_state.id)
        WHERE flow_run.id in (SELECT id from flow_run where state_name is null and state_id is not null limit 500);
    """

    update_task_run_state_name_in_batches = """
        UPDATE task_run
        SET state_name = (SELECT name from task_run_state where task_run.state_id = task_run_state.id)
        WHERE task_run.id in (SELECT id from task_run where state_name is null and state_id is not null limit 500);
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
