"""Add FlowRun.infrastructure_pid

Revision ID: 7201de756d85
Revises: 4f90ad6349bd
Create Date: 2022-11-18 16:13:32.195734

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7201de756d85"
down_revision = "4f90ad6349bd"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("infrastructure_pid", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("infrastructure_pid")
