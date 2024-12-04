"""Add `trigger_id` to the unique index for `automation_bucket`

Revision ID: 2b6c2b548f95
Revises: cc510aec4689
Create Date: 2024-04-09 13:18:32.041914

"""

import sqlalchemy as sa
from alembic import op

import prefect.server.utilities.database

# revision identifiers, used by Alembic.
revision = "2b6c2b548f95"
down_revision = "cc510aec4689"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("automation_bucket", schema=None) as batch_op:
        batch_op.alter_column(
            "trigger_id",
            existing_type=prefect.server.utilities.database.UUID(),
            nullable=False,
        )
        batch_op.alter_column(
            "triggered_at",
            existing_type=sa.TIMESTAMP(),
            type_=prefect.server.utilities.database.Timestamp(timezone=True),
            nullable=True,
        )
        batch_op.drop_index("uq_automation_bucket__automation_id__bucketing_key")
        batch_op.create_index(
            "uq_automation_bucket__automation_id__trigger_id__bucketing_key",
            ["automation_id", "trigger_id", "bucketing_key"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table("automation_bucket", schema=None) as batch_op:
        batch_op.drop_index(
            "uq_automation_bucket__automation_id__trigger_id__bucketing_key"
        )
        batch_op.create_index(
            "uq_automation_bucket__automation_id__bucketing_key",
            ["automation_id", "bucketing_key"],
            unique=1,
        )
        batch_op.alter_column(
            "trigger_id",
            existing_type=prefect.server.utilities.database.UUID(),
            nullable=True,
        )
        batch_op.alter_column(
            "triggered_at",
            existing_type=prefect.server.utilities.database.Timestamp(timezone=True),
            type_=sa.TIMESTAMP(),
            nullable=False,
        )
