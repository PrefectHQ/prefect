"""add_infra_overrides_to_flow_run

Revision ID: 2f527b22d5e5
Revises: 6b63c51c31b4
Create Date: 2024-01-18 23:28:11.408699

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import Text

import prefect

# revision identifiers, used by Alembic.
revision = "2f527b22d5e5"
down_revision = "6b63c51c31b4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "flow_run",
        sa.Column(
            "infra_overrides",
            prefect.server.utilities.database.JSON(astext_type=Text()),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("flow_run", "infra_overrides")
