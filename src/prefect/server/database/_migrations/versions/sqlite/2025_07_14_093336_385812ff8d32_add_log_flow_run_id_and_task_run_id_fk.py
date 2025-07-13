"""add_log_flow_run_id_and_task_run_id_fk

Revision ID: 385812ff8d32
Revises: 8bb517bae6f9
Create Date: 2025-07-14 09:33:36.223352

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "385812ff8d32"
down_revision = "8bb517bae6f9"
branch_labels = None
depends_on = None


def upgrade():
    # add foreign keys
    with op.batch_alter_table("log", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_log__task_run_id__task_run"),
            "task_run",
            ["task_run_id"],
            ["id"],
            ondelete="CASCADE",
            use_alter=True,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_log__flow_run_id__flow_run"),
            "flow_run",
            ["flow_run_id"],
            ["id"],
            ondelete="CASCADE",
            use_alter=True,
        )


def downgrade():
    # drop foreign keys
    with op.batch_alter_table("log", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_log__flow_run_id__flow_run"), type_="foreignkey"
        )
        batch_op.drop_constraint(
            batch_op.f("fk_log__task_run_id__task_run"), type_="foreignkey"
        )
