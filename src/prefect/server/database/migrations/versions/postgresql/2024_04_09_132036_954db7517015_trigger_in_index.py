"""Add `trigger_id` to the unique index for `automation_bucket`

Revision ID: 954db7517015
Revises: 916718e8330f
Create Date: 2024-04-09 13:20:36.838767

"""

from alembic import op

import prefect.server.utilities.database

# revision identifiers, used by Alembic.
revision = "954db7517015"
down_revision = "916718e8330f"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "automation_bucket",
        "trigger_id",
        existing_type=prefect.server.utilities.database.UUID(),
        nullable=False,
    )
    op.alter_column(
        "automation_bucket",
        "triggered_at",
        existing_type=prefect.server.utilities.database.Timestamp(timezone=True),
        nullable=True,
    )
    op.drop_index(
        "uq_automation_bucket__automation_id__bucketing_key",
        table_name="automation_bucket",
    )
    op.create_index(
        "uq_automation_bucket__automation_id__trigger_id__bucketing_key",
        "automation_bucket",
        ["automation_id", "trigger_id", "bucketing_key"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "uq_automation_bucket__automation_id__trigger_id__bucketing_key",
        table_name="automation_bucket",
    )
    op.create_index(
        "uq_automation_bucket__automation_id__bucketing_key",
        "automation_bucket",
        ["automation_id", "bucketing_key"],
        unique=True,
    )
    op.alter_column(
        "automation_bucket",
        "triggered_at",
        existing_type=prefect.server.utilities.database.Timestamp(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "automation_bucket",
        "trigger_id",
        existing_type=prefect.server.utilities.database.UUID(),
        nullable=True,
    )
