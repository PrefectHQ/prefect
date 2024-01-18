"""add_infra_overrides_to_flow_run

Revision ID: ee97fbae08cd
Revises: c63a0a6dc787
Create Date: 2024-01-18 23:32:28.912065

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text

import prefect

# revision identifiers, used by Alembic.
revision = "ee97fbae08cd"
down_revision = "c63a0a6dc787"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "infra_overrides",
                prefect.server.utilities.database.JSON(astext_type=Text()),
                server_default="{}",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("infra_overrides")
