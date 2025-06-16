"""Drop task_run state_id foreign key constraint

Revision ID: 3b86c5ea017a
Revises: aa1234567890
Create Date: 2025-06-13 16:06:44.950314

"""

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
    # Re-add the foreign key constraint
    op.create_foreign_key(
        "fk_task_run__state_id__task_run_state",
        "task_run",
        "task_run_state",
        ["state_id"],
        ["id"],
        ondelete="SET NULL",
    )
