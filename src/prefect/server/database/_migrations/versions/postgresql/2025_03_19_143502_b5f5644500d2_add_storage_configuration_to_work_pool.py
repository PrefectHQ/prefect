"""add storage configuration to work pool

Revision ID: b5f5644500d2
Revises: a03d00b8e275
Create Date: 2025-03-19 14:35:02.405170

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "b5f5644500d2"
down_revision = "a03d00b8e275"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "work_pool",
        sa.Column(
            "storage_configuration",
            prefect.server.utilities.database.Pydantic(
                prefect.server.schemas.core.WorkPoolStorageConfiguration
            ),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("work_pool", "storage_configuration")
