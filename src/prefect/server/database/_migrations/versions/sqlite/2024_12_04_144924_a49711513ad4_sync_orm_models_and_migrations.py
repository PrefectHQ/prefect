"""Sync ORM models and migrations

Revision ID: a49711513ad4
Revises: 5952a5498b51
Create Date: 2024-12-04 14:49:24.099491

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = "a49711513ad4"
down_revision = "5952a5498b51"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("artifact_collection", schema=None) as batch_op:
        # table added in 027c123512befd2bd00a0ef28bd44215e77bece6 but index was
        # never created in a migration.
        batch_op.create_index(
            batch_op.f("ix_artifact_collection__updated"), ["updated"], unique=False
        )
        # index created on the wrong table in ca9f93463a4c38fce8be972d91e808b5935e5d9c
        batch_op.drop_index("ix_artifact__key_created_desc")

    with op.batch_alter_table("artifact", schema=None) as batch_op:
        # index created on the wrong table in ca9f93463a4c38fce8be972d91e808b5935e5d9c
        batch_op.create_index(
            "ix_artifact__key_created_desc",
            ["key", sa.text("created DESC")],
            unique=False,
            postgresql_include=["id", "updated", "type", "task_run_id", "flow_run_id"],
        )

    with op.batch_alter_table("block_document", schema=None) as batch_op:
        # Renamed index to remain consistent with PostgreSQL
        batch_op.drop_index("ix_block_document__block_type_name_name")
        batch_op.create_index(
            "ix_block_document__block_type_name__name",
            ["block_type_name", "name"],
            unique=False,
        )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        # columns removed in c53b00bfa1f6850ab43e168c92c627350c090647
        batch_op.drop_column("schedule")
        batch_op.drop_column("is_schedule_active")

        # column removed in 5784c637e7e11a8e88e2b3146e54e9b6c97d50ef
        batch_op.drop_column("flow_data")

        # column removed in eaa7a5063c73718dff56ce4aeb66e53fcafe60e5
        batch_op.drop_column("manifest_path")

    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        # columns removed from orm models in 0b62de684447c6955e04c722c276edac4002fd40
        batch_op.drop_column("catchup")
        batch_op.drop_column("max_active_runs")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        # Column is no longer a FK since d10c7471a69403bcf88f401091497a2dc8963885
        batch_op.drop_index("ix_flow_run__deployment_id")
        # Index accidentally dropped in 519a2ed6e31e2b60136e1a1a163a9cd0a8d3d5c4
        batch_op.create_index(
            "ix_flow_run__scheduler_deployment_id_auto_scheduled_next_schedu",
            ["deployment_id", "auto_scheduled", "next_scheduled_start_time"],
            unique=False,
            postgresql_where=sa.text("state_type = 'SCHEDULED'::state_type"),
            sqlite_where=sa.text("state_type = 'SCHEDULED'"),
        )


def downgrade():
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index(
            "ix_flow_run__scheduler_deployment_id_auto_scheduled_next_schedu",
            postgresql_where=sa.text("state_type = 'SCHEDULED'::state_type"),
            sqlite_where=sa.text("state_type = 'SCHEDULED'"),
        )
        batch_op.create_index(
            "ix_flow_run__deployment_id", ["deployment_id"], unique=False
        )

    with op.batch_alter_table("deployment_schedule", schema=None) as batch_op:
        batch_op.add_column(sa.Column("max_active_runs", sa.INTEGER(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "catchup", sa.BOOLEAN(), server_default=sa.text("'0'"), nullable=False
            )
        )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_schedule_active",
                sa.BOOLEAN(),
                server_default=sa.text("'1'"),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("flow_data", sqlite.JSON(), nullable=True))
        batch_op.add_column(sa.Column("schedule", sqlite.JSON(), nullable=True))
        batch_op.add_column(sa.Column("manifest_path", sa.VARCHAR(), nullable=True))

    with op.batch_alter_table("block_document", schema=None) as batch_op:
        batch_op.drop_index("ix_block_document__block_type_name__name")
        batch_op.create_index(
            "ix_block_document__block_type_name_name",
            ["block_type_name", "name"],
            unique=False,
        )

    with op.batch_alter_table("artifact", schema=None) as batch_op:
        batch_op.drop_index(
            "ix_artifact__key_created_desc",
            postgresql_include=["id", "updated", "type", "task_run_id", "flow_run_id"],
        )

    with op.batch_alter_table("artifact_collection", schema=None) as batch_op:
        batch_op.create_index(
            "ix_artifact__key_created_desc", ["key", "created"], unique=False
        )
        batch_op.drop_index(batch_op.f("ix_artifact_collection__updated"))
