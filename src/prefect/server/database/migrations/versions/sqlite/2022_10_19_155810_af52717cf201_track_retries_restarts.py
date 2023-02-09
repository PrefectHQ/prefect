"""Add retry and restart metadata

Revision ID: af52717cf201
Revises: ad4b1b4d1e9d
Create Date: 2022-10-19 15:58:10.016251

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "af52717cf201"
down_revision = "3ced59d8806b"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "flow_run_run_count", sa.Integer(), server_default="0", nullable=False
            )
        )

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.drop_column("flow_run_run_count")

    # ### end Alembic commands ###
