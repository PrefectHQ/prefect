"""add_disabled_to_deployment

Revision ID: 3cc41614eec4
Revises: 94622c1663e8
Create Date: 2024-07-12 12:41:02.758100

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "3cc41614eec4"
down_revision = "94622c1663e8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column("disabled", sa.Boolean(), server_default="0", nullable=False),
    )
    op.execute("ALTER TYPE deployment_status_type ADD VALUE IF NOT EXISTS 'DISABLED';")


def downgrade():
    op.drop_column("deployment", "disabled")
