"""add tags to automation

Revision ID: abc123def456
Revises: 1c9bb7f78263
Create Date: 2025-06-12 20:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "abc123def456"
down_revision = "1c9bb7f78263"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "automation", sa.Column("tags", sa.JSON(), server_default="[]", nullable=False)
    )


def downgrade():
    op.drop_column("automation", "tags")
