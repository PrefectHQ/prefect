"""Add flow_run.state_name

Revision ID: 605ebb4e9155
Revises: 2e7e1428ffce
Create Date: 2022-04-20 11:30:11.934795

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "605ebb4e9155"
down_revision = "2e7e1428ffce"
branch_labels = None
depends_on = None


def upgrade():

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("state_name", sa.String(), nullable=True))
        batch_op.create_index("ix_flow_run__state_name", ["state_name"], unique=False)

    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("state_name", sa.String(), nullable=True))
        batch_op.create_index("ix_task_run__state_name", ["state_name"], unique=False)

    # backfill flow_run.state_name in batches
    conn = op.get_bind()
    update_flow_run_state_name_in_batches = """
    WITH null_flow_run_state_name_cte as (SELECT id from flow_run where state_name is null limit 500)
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

    # back fill task_run.state_name in batches
    update_task_run_state_name_in_batches = """
    WITH null_task_run_state_name_cte as (SELECT id from task_run where state_name is null limit 500)
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
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.drop_index("ix_task_run__state_name")
        batch_op.drop_column("state_name")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__state_name")
        batch_op.drop_column("state_name")
