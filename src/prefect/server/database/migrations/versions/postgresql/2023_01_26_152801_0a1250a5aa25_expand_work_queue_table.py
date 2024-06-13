"""Expand work queue table

Revision ID: 0a1250a5aa25
Revises: d481d5058a19
Create Date: 2023-01-25 15:28:01.263916

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "0a1250a5aa25"
down_revision = "2882cd2df466"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_constraint("fk_work_pool__default_queue_id__work_pool_queue")
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_index("ix_deployment__work_pool_queue_id")
        batch_op.drop_column("work_pool_queue_id")
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__work_pool_queue_id")
        batch_op.drop_column("work_pool_queue_id")

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
                "work_pool_id", prefect.server.utilities.database.UUID(), nullable=True
            )
        )

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "work_queue_id",
                prefect.server.utilities.database.UUID(),
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
                prefect.server.utilities.database.UUID(),
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
        batch_op.alter_column("type", nullable=False)

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_work_queue__work_pool_id__work_pool"),
            "work_pool",
            ["work_pool_id"],
            ["id"],
            ondelete="cascade",
        )

        batch_op.create_index(
            op.f("ix_work_queue__work_pool_id"),
            ["work_pool_id"],
            unique=False,
        )
        batch_op.create_index(
            op.f("ix_work_queue__work_pool_id_priority"),
            ["work_pool_id", "priority"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_index("ix_work_queue__work_pool_id_priority")
        batch_op.drop_index("ix_work_queue__work_pool_id")
        batch_op.drop_constraint("fk_work_queue__work_pool_id__work_pool")

    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_constraint("fk_work_pool__default_queue_id__work_queue")
        batch_op.alter_column("type", nullable=True)

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_constraint("fk_deployment__work_queue_id__work_queue")
        batch_op.drop_index("ix_deployment__work_queue_id")
        batch_op.drop_column("work_queue_id")

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_constraint("fk_flow_run__work_queue_id__work_queue")
        batch_op.drop_index("ix_flow_run__work_queue_id")
        batch_op.drop_column("work_queue_id")

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_column("work_pool_id")
        batch_op.drop_column("priority")

    op.execute(sa.text("DELETE FROM work_pool"))

    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_work_pool__default_queue_id__work_pool_queue"),
            "work_pool_queue",
            ["default_queue_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "work_pool_queue_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_deployment__work_pool_queue_id"),
            ["work_pool_queue_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__work_pool_queue_id__work_pool_queue"),
            "work_pool_queue",
            ["work_pool_queue_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "work_pool_queue_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_flow_run__work_pool_queue_id"),
            ["work_pool_queue_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_flow_run__work_pool_queue_id__work_pool_queue"),
            "work_pool_queue",
            ["work_pool_queue_id"],
            ["id"],
            ondelete="SET NULL",
        )
