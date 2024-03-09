"""Add job_variables column to flow-runs

Revision ID: 342220764f0b
Revises: 265eb1a2da4c
Create Date: 2024-03-05 11:52:58.330563

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text

import prefect

# revision identifiers, used by Alembic.
revision = "342220764f0b"
down_revision = "265eb1a2da4c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run",
        sa.Column(
            "job_variables",
            prefect.server.utilities.database.JSON(astext_type=Text()),
            server_default="{}",
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("flow_run", "job_variables")
