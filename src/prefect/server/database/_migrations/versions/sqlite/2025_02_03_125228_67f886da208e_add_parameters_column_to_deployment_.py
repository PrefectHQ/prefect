"""Add parameters column to deployment schedules

Revision ID: 67f886da208e
Revises: a49711513ad4
Create Date: 2025-02-03 12:52:28.370958

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "67f886da208e"
down_revision = "a49711513ad4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment_schedule",
        sa.Column(
            "parameters",
            prefect.server.utilities.database.JSON,
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("deployment_schedule", "parameters")
