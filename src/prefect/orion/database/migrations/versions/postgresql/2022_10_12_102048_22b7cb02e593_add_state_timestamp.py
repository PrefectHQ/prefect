"""Add state_timestamp

Revision ID: 22b7cb02e593
Revises: 2d5e000696f1
Create Date: 2022-10-12 10:20:48.760447

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "22b7cb02e593"
down_revision = "2d5e000696f1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "state_timestamp",
                prefect.orion.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_flow_run__state_timestamp", ["state_timestamp"], unique=False
        )

    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "state_timestamp",
                prefect.orion.utilities.database.Timestamp(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_task_run__state_timestamp", ["state_timestamp"], unique=False
        )

    update_flow_run_state_timestamp_in_batches = """
        WITH null_flow_run_state_timestamp_cte as (SELECT id from flow_run where state_timestamp is null and state_id is not null limit 500)
        UPDATE flow_run
        SET state_timestamp = flow_run_state.timestamp
        FROM flow_run_state, null_flow_run_state_timestamp_cte
        WHERE flow_run.state_id = flow_run_state.id
        AND flow_run.id = null_flow_run_state_timestamp_cte.id;
    """

    update_task_run_state_timestamp_in_batches = """
        WITH null_task_run_state_timestamp_cte as (SELECT id from task_run where state_timestamp is null and state_id is not null limit 500)
        UPDATE task_run
        SET state_timestamp = task_run_state.timestamp
        FROM task_run_state, null_task_run_state_timestamp_cte
        WHERE task_run.state_id = task_run_state.id
        AND task_run.id = null_task_run_state_timestamp_cte.id;
    """

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        while True:
            # execute until we've backfilled all flow run state timestamps
            # autocommit mode will commit each time `execute` is called
            result = conn.execute(sa.text(update_flow_run_state_timestamp_in_batches))
            if result.rowcount <= 0:
                break

        while True:
            # execute until we've backfilled all task run state timestamps
            # autocommit mode will commit each time `execute` is called
            result = conn.execute(sa.text(update_task_run_state_timestamp_in_batches))
            if result.rowcount <= 0:
                break


def downgrade():
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.drop_index("ix_task_run__state_timestamp")
        batch_op.drop_column("state_timestamp")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__state_timestamp")
        batch_op.drop_column("state_timestamp")
