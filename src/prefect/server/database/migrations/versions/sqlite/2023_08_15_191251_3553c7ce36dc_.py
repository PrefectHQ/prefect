"""Make flow run id nullable

Revision ID: 3553c7ce36dc
Revises: 5b0bd3b41a23
Create Date: 2023-08-15 19:12:51.137743

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '3553c7ce36dc'
down_revision = '5b0bd3b41a23'
branch_labels = None
depends_on = None




def upgrade():
    with op.batch_alter_table("task_run") as batch_op:
        batch_op.alter_column("flow_run_id", nullable=True)

    with op.batch_alter_table("log") as batch_op:
        batch_op.alter_column("flow_run_id", nullable=True)


def downgrade():
    pass
