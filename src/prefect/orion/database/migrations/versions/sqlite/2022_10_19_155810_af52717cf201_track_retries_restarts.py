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
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("restarts", sa.Integer(), server_default="0", nullable=False)
        )

    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "flow_retry_attempt", sa.Integer(), server_default="0", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "flow_restart_attempt", sa.Integer(), server_default="0", nullable=False
            )
        )

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table("task_run", schema=None) as batch_op:
        batch_op.drop_column("flow_restart_attempt")
        batch_op.drop_column("flow_retry_attempt")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("restarts")

    # ### end Alembic commands ###
