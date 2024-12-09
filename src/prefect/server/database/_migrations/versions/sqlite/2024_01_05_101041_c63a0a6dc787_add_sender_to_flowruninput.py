"""Add `sender` to `FlowRunInput`

Revision ID: c63a0a6dc787
Revises: 35659cc49969
Create Date: 2024-01-05 10:10:41.226754

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c63a0a6dc787"
down_revision = "35659cc49969"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run_input", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sender", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("flow_run_input", schema=None) as batch_op:
        batch_op.drop_column("sender")
