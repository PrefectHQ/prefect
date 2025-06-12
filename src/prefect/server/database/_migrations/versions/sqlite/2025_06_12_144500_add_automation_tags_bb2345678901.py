"""Add tags column to automation table

Revision ID: bb2345678901
Revises: 3c841a1800a1
Create Date: 2025-06-12 14:45:00.000000

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "bb2345678901"
down_revision = "3c841a1800a1"
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
