"""Adds enforce_parameter_schema column to deployment table

Revision ID: db0eb3973a54
Revises: 50f8c182c3ca
Create Date: 2023-09-20 13:45:44.137095

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "db0eb3973a54"
down_revision = "50f8c182c3ca"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "deployment",
        sa.Column(
            "enforce_parameter_schema", sa.Boolean(), server_default="0", nullable=False
        ),
    )


def downgrade():
    op.drop_column("deployment", "enforce_parameter_schema")
