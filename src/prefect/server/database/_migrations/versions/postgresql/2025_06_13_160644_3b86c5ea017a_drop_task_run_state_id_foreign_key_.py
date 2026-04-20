"""Drop task_run state_id foreign key constraint

Revision ID: 3b86c5ea017a
Revises: aa1234567890
Create Date: 2025-06-13 16:06:44.950314

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3b86c5ea017a"
down_revision = "aa1234567890"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the foreign key constraint from task_run.state_id to task_run_state.id
    op.drop_constraint(
        "fk_task_run__state_id__task_run_state", "task_run", type_="foreignkey"
    )


def downgrade():
    # Null out any task_run.state_id values that reference non-existent
    # task_run_state rows. After the FK was dropped (upgrade), the system no
    # longer enforces referential integrity, so orphaned references are
    # expected. Without this cleanup, re-adding the FK would fail with an
    # IntegrityError on PostgreSQL.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE task_run
            SET state_id = NULL
            WHERE state_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM task_run_state
                  WHERE task_run_state.id = task_run.state_id
              )
            """
        )
    )

    # Re-add the foreign key constraint
    op.create_foreign_key(
        "fk_task_run__state_id__task_run_state",
        "task_run",
        "task_run_state",
        ["state_id"],
        ["id"],
        ondelete="SET NULL",
    )
