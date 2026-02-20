"""Add expression index for per-schedule scheduler query

Revision ID: a1b2c3d4e5f7
Revises: 9e83011d1f2a
Create Date: 2026-02-19 20:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "9e83011d1f2a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_flow_run__schedule_id_scheduler
        ON flow_run (deployment_id, json_extract(created_by, '$.id'), next_scheduled_start_time)
        WHERE state_type = 'SCHEDULED' AND auto_scheduled = 1;
        """
    )


def downgrade():
    op.execute(
        """
        DROP INDEX IF EXISTS ix_flow_run__schedule_id_scheduler;
        """
    )
