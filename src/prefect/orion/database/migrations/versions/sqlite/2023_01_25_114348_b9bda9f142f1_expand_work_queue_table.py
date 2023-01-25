"""Expand work queue table

Revision ID: b9bda9f142f1
Revises: bb38729c471a
Create Date: 2023-01-25 11:43:48.160070

"""
from alembic import op
import sqlalchemy as sa
import prefect


# revision identifiers, used by Alembic.
revision = "b9bda9f142f1"
down_revision = "bb38729c471a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    # dropping columns to efficiently clear indexes and constraints
    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_constraint("fk_work_pool__default_queue_id__work_pool_queue")
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_index("ix_deployment__work_pool_queue_id")
        batch_op.drop_column("work_pool_queue_id")
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__work_pool_queue_id")
        batch_op.drop_column("work_pool_queue_id")

    op.drop_table("work_pool_queue")

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "priority",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.add_column(
            sa.Column(
                "work_pool_id", prefect.orion.utilities.database.UUID(), nullable=False
            )
        )

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "work_queue_id",
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_flow_run__work_queue_id"),
            ["work_queue_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_flow_run__work_queue_id__work_queue"),
            "work_queue",
            ["work_queue_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "work_queue_id",
                prefect.orion.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_deployment__work_queue_id"),
            ["work_queue_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__work_queue_id__work_queue"),
            "work_queue",
            ["work_queue_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_work_pool__default_queue_id__work_queue"),
            "work_queue",
            ["default_queue_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_work_queue__work_pool_id__work_pool"),
            "work_pool",
            ["work_pool_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    pass
