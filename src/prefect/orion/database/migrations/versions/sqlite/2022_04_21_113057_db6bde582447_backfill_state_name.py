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
    conn = op.get_bind()

    update_flow_run_state_name_in_batches = """
        WITH null_flow_run_state_name_cte as (SELECT id from flow_run where state_name is null and state_id is not null limit 500)
        UPDATE flow_run
        SET state_name = flow_run_state.name
        FROM flow_run_state, null_flow_run_state_name_cte
        WHERE flow_run.state_id = flow_run_state.id
        AND flow_run.id = null_flow_run_state_name_cte.id;
    """

    result = conn.execute(sa.text(update_flow_run_state_name_in_batches))
    while True:
        if result.rowcount <= 0:
            break

    update_task_run_state_name_in_batches = """
        WITH null_task_run_state_name_cte as (SELECT id from task_run where state_name is null and state_id is not null limit 500)
        UPDATE task_run
        SET state_name = task_run_state.name
        FROM task_run_state, null_task_run_state_name_cte
        WHERE task_run.state_id = task_run_state.id
        AND task_run.id = null_task_run_state_name_cte.id;
    """

    result = conn.execute(sa.text(update_task_run_state_name_in_batches))
    while True:
        if result.rowcount <= 0:
            break


def downgrade():
    """
    Data only migration. No action on downgrade.
    """
    pass
