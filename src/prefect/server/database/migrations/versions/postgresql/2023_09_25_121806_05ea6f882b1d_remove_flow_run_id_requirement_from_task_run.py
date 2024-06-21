"""Make flow_run_id nullable on task_run and log tables

Revision ID: 05ea6f882b1d
Revises: 4e9a6f93eb6c
Create Date: 2023-09-25 12:18:06.722322

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "05ea6f882b1d"
down_revision = "4e9a6f93eb6c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("task_run") as batch_op:
        batch_op.alter_column("flow_run_id", nullable=True)

    with op.batch_alter_table("log") as batch_op:
        batch_op.alter_column("flow_run_id", nullable=True)


def downgrade():
    with op.batch_alter_table("task_run") as batch_op:
        batch_op.alter_column("flow_run_id", nullable=False)

    with op.batch_alter_table("log") as batch_op:
        batch_op.alter_column("flow_run_id", nullable=False)
