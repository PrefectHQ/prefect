"""Add tags column to automation table

Revision ID: aa1234567890
Revises: 1c9bb7f78263
Create Date: 2025-06-12 14:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "aa1234567890"
down_revision = "1c9bb7f78263"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "automation",
        sa.Column(
            "tags",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("automation", "tags")
