"""Drop task_run state_id foreign key constraint

Revision ID: 8bb517bae6f9
Revises: bb2345678901
Create Date: 2025-06-13 16:45:06.404249

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "8bb517bae6f9"
down_revision = "bb2345678901"
branch_labels = None
depends_on = None


def upgrade():
    # Drop the foreign key constraint from task_run.state_id to task_run_state.id
    with op.batch_alter_table("task_run") as batch_op:
        batch_op.drop_constraint("fk_task_run__state_id__task_run_state")


def downgrade():
    # Re-add the foreign key constraint
    with op.batch_alter_table("task_run") as batch_op:
        batch_op.create_foreign_key(
            "fk_task_run__state_id__task_run_state",
            "task_run_state",
            ["state_id"],
            ["id"],
            ondelete="SET NULL",
        )
