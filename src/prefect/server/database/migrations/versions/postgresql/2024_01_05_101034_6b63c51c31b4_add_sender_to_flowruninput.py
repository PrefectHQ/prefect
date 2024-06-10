"""Add `sender` to `FlowRunInput`

Revision ID: 6b63c51c31b4
Revises: 7c453555d3a5
Create Date: 2024-01-05 10:10:34.201651

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6b63c51c31b4"
down_revision = "7c453555d3a5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("flow_run_input", sa.Column("sender", sa.String(), nullable=True))


def downgrade():
    op.drop_column("flow_run_input", "sender")
