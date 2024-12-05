"""Sync ORM models and migrations

Revision ID: 5d03c01be85e
Revises: 68a44144428d
Create Date: 2024-12-04 16:53:33.015870

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "5d03c01be85e"
down_revision = "68a44144428d"
branch_labels = None
depends_on = None


def upgrade():
    # Column is non-null in the ORM and in SQLite.
    op.execute(
        "UPDATE artifact_collection SET latest_id=GEN_RANDOM_UUID() WHERE latest_id IS NULL"
    )
    op.alter_column(
        "artifact_collection", "latest_id", existing_type=sa.UUID(), nullable=False
    )

    # table added in 027c123512befd2bd00a0ef28bd44215e77bece6 but index was
    # never created in a migration.
    op.create_index(
        op.f("ix_artifact_collection__updated"),
        "artifact_collection",
        ["updated"],
        unique=False,
    )

    # columns removed in c53b00bfa1f6850ab43e168c92c627350c090647
    op.drop_column("deployment", "schedule")
    op.drop_column("deployment", "is_schedule_active")

    # column removed in 5784c637e7e11a8e88e2b3146e54e9b6c97d50ef
    op.drop_column("deployment", "flow_data")

    # Column is no longer a FK since d10c7471a69403bcf88f401091497a2dc8963885
    op.drop_index("ix_flow_run__deployment_id", table_name="flow_run")

    # column removed in eaa7a5063c73718dff56ce4aeb66e53fcafe60e5
    op.drop_column("deployment", "manifest_path")

    # columns removed from orm models in 0b62de684447c6955e04c722c276edac4002fd40
    op.drop_column("deployment_schedule", "catchup")
    op.drop_column("deployment_schedule", "max_active_runs")


def downgrade():
    op.create_index(
        "ix_flow_run__deployment_id", "flow_run", ["deployment_id"], unique=False
    )
    op.add_column(
        "deployment_schedule",
        sa.Column("max_active_runs", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "deployment_schedule",
        sa.Column(
            "catchup",
            sa.BOOLEAN(),
            server_default=sa.text("false"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "deployment",
        sa.Column(
            "flow_data",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column(
        "deployment",
        sa.Column(
            "is_schedule_active",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            autoincrement=False,
            nullable=False,
        ),
    )
    op.add_column(
        "deployment",
        sa.Column("manifest_path", sa.VARCHAR(), autoincrement=False, nullable=True),
    )
    op.add_column(
        "deployment",
        sa.Column(
            "schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.drop_index(
        op.f("ix_artifact_collection__updated"), table_name="artifact_collection"
    )
    op.alter_column(
        "artifact_collection", "latest_id", existing_type=sa.UUID(), nullable=True
    )
