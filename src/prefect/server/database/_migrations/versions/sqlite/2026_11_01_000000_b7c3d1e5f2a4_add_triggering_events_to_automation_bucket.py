"""Add triggering_events column to automation_bucket table

Revision ID: b7c3d1e5f2a4
Revises: 27d8f4e1a6c9
Create Date: 2026-11-01 00:00:00.000000

Retains the events a bucket counted, so a firing can expose every
contributing event to an action template instead of only the last one.
"""

import sqlalchemy as sa
from alembic import op

import prefect.server.utilities.database

# revision identifiers, used by Alembic.
revision = "b7c3d1e5f2a4"
down_revision = "27d8f4e1a6c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "automation_bucket",
        sa.Column(
            "triggering_events",
            prefect.server.utilities.database.JSON(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("automation_bucket", "triggering_events")
