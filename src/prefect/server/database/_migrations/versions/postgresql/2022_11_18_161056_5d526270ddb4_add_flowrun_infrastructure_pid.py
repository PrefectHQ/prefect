"""Add FlowRun.infrastructure_pid

Revision ID: 5d526270ddb4
Revises: 8caf7c1fd82c
Create Date: 2022-11-18 16:10:56.397525

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5d526270ddb4"
down_revision = "8caf7c1fd82c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(sa.Column("infrastructure_pid", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("infrastructure_pid")
