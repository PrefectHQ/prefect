"""Adds enforce_parameter_schema column to deployment table

Revision ID: ef674d598dd3
Revises: c2d001b7dd06
Create Date: 2023-09-20 13:41:45.875549

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ef674d598dd3"
down_revision = "c2d001b7dd06"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "enforce_parameter_schema",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("enforce_parameter_schema")
