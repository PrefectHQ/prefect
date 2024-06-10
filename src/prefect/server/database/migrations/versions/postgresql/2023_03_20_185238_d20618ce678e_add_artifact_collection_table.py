"""Add artifact_collection table
Revision ID: d20618ce678e
Revises: aa84ac237ce8
# create date: 185238
Create Date: 2023-03-20 18:52:38.438841
"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "d20618ce678e"
down_revision = "aa84ac237ce8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artifact_collection",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("latest_id", prefect.server.utilities.database.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_collection")),
        sa.UniqueConstraint("key", name=op.f("uq_artifact_collection__key")),
    )

    op.create_index(
        op.f("ix_artifact_collection__key_latest_id"),
        "artifact_collection",
        ["key", "latest_id"],
    )


def downgrade():
    op.drop_index(
        op.f("ix_artifact_collection__key_latest_id"), table_name="artifact_collection"
    )
    op.drop_table("artifact_collection")
