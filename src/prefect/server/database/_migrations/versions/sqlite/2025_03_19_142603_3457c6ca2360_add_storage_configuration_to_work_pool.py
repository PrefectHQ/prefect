"""add storage configuration to work pool

Revision ID: 3457c6ca2360
Revises: 07ecde74d74d
Create Date: 2025-03-19 14:26:03.618303

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "3457c6ca2360"
down_revision = "07ecde74d74d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "storage_configuration",
                prefect.server.utilities.database.Pydantic(
                    prefect.server.schemas.core.WorkPoolStorageConfiguration
                ),
                server_default="{}",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_column("storage_configuration")
