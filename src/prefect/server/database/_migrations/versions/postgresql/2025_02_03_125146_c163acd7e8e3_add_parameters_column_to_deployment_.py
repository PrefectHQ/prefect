"""Add parameters column to deployment schedules

Revision ID: c163acd7e8e3
Revises: 5d03c01be85e
Create Date: 2025-02-03 12:51:46.641928

"""
from alembic import op
import sqlalchemy as sa
import prefect.server.database.utilities import JSON

# revision identifiers, used by Alembic.
revision = 'c163acd7e8e3'
down_revision = '5d03c01be85e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment_schedule",
        sa.Column("parameters", JSON, server_default="{}", nullable=False),
    )


def downgrade():
    op.drop_column("deployment_schedule", "parameters")
