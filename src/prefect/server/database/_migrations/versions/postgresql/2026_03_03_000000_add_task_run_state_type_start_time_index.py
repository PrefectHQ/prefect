"""Add composite index on task_run(state_type, start_time)

Revision ID: 09a9e091e578
Revises: a1b2c3d4e5f6
Create Date: 2026-03-03 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "09a9e091e578"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
            ix_task_run__state_type_start_time
            ON task_run (state_type, start_time)
            """
        )


def downgrade():
    with op.get_context().autocommit_block():
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_task_run__state_type_start_time"
        )
