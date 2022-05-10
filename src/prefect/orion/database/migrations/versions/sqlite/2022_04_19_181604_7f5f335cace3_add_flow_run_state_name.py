"""Add flow_run.state_name

Revision ID: 7f5f335cace3
Revises: 71a57ec351d1
Create Date: 2022-04-19 18:16:04.893465

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7f5f335cace3"
down_revision = "71a57ec351d1"
branch_labels = None
depends_on = None


def upgrade():

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("state_name", sa.String(), nullable=True))
        batch_op.create_index("ix_flow_run__state_name", ["state_name"], unique=False)

    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("state_name", sa.String(), nullable=True))
        batch_op.create_index("ix_task_run__state_name", ["state_name"], unique=False)


def downgrade():
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.drop_index("ix_task_run__state_name")
        batch_op.drop_column("state_name")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__state_name")
        batch_op.drop_column("state_name")
