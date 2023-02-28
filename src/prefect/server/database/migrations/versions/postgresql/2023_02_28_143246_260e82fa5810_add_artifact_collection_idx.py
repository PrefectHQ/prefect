"""Add artifact_collection indexes

Revision ID: 260e82fa5810
Revises: d20618ce678e
Create Date: 2023-02-28 14:32:46.472765

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "260e82fa5810"
down_revision = "d20618ce678e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_artifact_collection__latest_id",
        "artifact_collection",
        ["latest_id"],
        unique=False,
    )
    op.create_index(
        "uq_artifact_collection__key", "artifact_collection", ["key"], unique=True
    )


def downgrade():
    op.drop_index("uq_artifact_collection__key", table_name="artifact_collection")
    op.drop_index("ix_artifact_collection__latest_id", table_name="artifact_collection")
