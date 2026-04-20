"""Add composite index on task_run(state_type, start_time)

Revision ID: 4dfa692e02a7
Revises: a1b2c3d4e5f7
Create Date: 2026-03-03 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "4dfa692e02a7"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_task_run__state_type_start_time
        ON task_run (state_type, start_time)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_task_run__state_type_start_time")
