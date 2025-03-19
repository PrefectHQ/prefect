"""Add storage configuration to work pool

Revision ID: 40f679df41e9
Revises: 07ecde74d74d
Create Date: 2025-03-19 13:41:38.864798

"""

import sqlalchemy as sa
from alembic import op

from prefect.server.schemas.core import WorkPoolStorageConfiguration
from prefect.server.utilities.database import Pydantic

# revision identifiers, used by Alembic.
revision = "40f679df41e9"
down_revision = "07ecde74d74d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "work_pool",
        sa.Column(
            "storage_configuration",
            Pydantic(WorkPoolStorageConfiguration),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("work_pool", "storage_configuration")
