"""Rename Worker Pools to Work Pools

Revision ID: d481d5058a19
Revises: f7587d6c5776
Create Date: 2023-01-08 18:01:42.559990

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "d481d5058a19"
down_revision = "f7587d6c5776"
branch_labels = None
depends_on = None


def upgrade():
    # delete old worker table structures
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("worker_pool_queue_id")
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("worker_pool_queue_id")
    with op.batch_alter_table("worker_pool", schema=None) as batch_op:
        batch_op.drop_constraint("fk_worker_pool__default_queue_id__worker_pool_queue")
    op.drop_table("worker_pool_queue")
    op.drop_table("worker")
    op.drop_table("worker_pool")

    op.create_table(
        "work_pool",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column(
            "base_job_template",
            prefect.server.utilities.database.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_paused", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column(
            "default_queue_id", prefect.server.utilities.database.UUID(), nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_pool")),
        sa.UniqueConstraint("name", name=op.f("uq_work_pool__name")),
    )
    op.create_index(
        op.f("ix_work_pool__updated"), "work_pool", ["updated"], unique=False
    )
    op.create_index(op.f("ix_work_pool__type"), "work_pool", ["type"], unique=False)

    op.create_table(
        "worker",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "last_heartbeat_time",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "work_pool_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_pool_id"],
            ["work_pool.id"],
            name=op.f("fk_worker__work_pool_id__work_pool"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker")),
        sa.UniqueConstraint(
            "work_pool_id",
            "name",
            name=op.f("uq_worker__work_pool_id_name"),
        ),
    )
    op.create_index(op.f("ix_worker__updated"), "worker", ["updated"], unique=False)
    op.create_index(
        op.f("ix_worker__work_pool_id"),
        "worker",
        ["work_pool_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker__work_pool_id_last_heartbeat_time"),
        "worker",
        ["work_pool_id", "last_heartbeat_time"],
        unique=False,
    )

    op.create_table(
        "work_pool_queue",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_paused", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "work_pool_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["work_pool_id"],
            ["work_pool.id"],
            name=op.f("fk_work_pool_queue__work_pool_id__work_pool"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_pool_queue")),
        sa.UniqueConstraint(
            "work_pool_id",
            "name",
            name=op.f("uq_work_pool_queue__work_pool_id_name"),
        ),
    )
    op.create_index(
        op.f("ix_work_pool_queue__updated"),
        "work_pool_queue",
        ["updated"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_pool_queue__work_pool_id_priority"),
        "work_pool_queue",
        ["work_pool_id", "priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_work_pool_queue__work_pool_id"),
        "work_pool_queue",
        ["work_pool_id"],
        unique=False,
    )

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


def downgrade():
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_column("work_pool_queue_id")
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_column("work_pool_queue_id")
    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_constraint("fk_work_pool__default_queue_id__work_pool_queue")
    op.drop_table("work_pool_queue")
    op.drop_table("worker")
    op.drop_table("work_pool")

    # recreate old table structure
    op.create_table(
        "worker_pool",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column(
            "base_job_template",
            prefect.server.utilities.database.JSON(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_paused", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column(
            "default_queue_id", prefect.server.utilities.database.UUID(), nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_pool")),
        sa.UniqueConstraint("name", name=op.f("uq_worker_pool__name")),
    )
    op.create_index(
        op.f("ix_worker_pool__updated"), "worker_pool", ["updated"], unique=False
    )
    op.create_index(op.f("ix_worker_pool__type"), "worker_pool", ["type"], unique=False)

    op.create_table(
        "worker",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "last_heartbeat_time",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "worker_pool_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["worker_pool_id"],
            ["worker_pool.id"],
            name=op.f("fk_worker__worker_pool_id__worker_pool"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker")),
        sa.UniqueConstraint(
            "worker_pool_id",
            "name",
            name=op.f("uq_worker__worker_pool_id_name"),
        ),
    )
    op.create_index(op.f("ix_worker__updated"), "worker", ["updated"], unique=False)
    op.create_index(
        op.f("ix_worker__worker_pool_id"),
        "worker",
        ["worker_pool_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker__worker_pool_id_last_heartbeat_time"),
        "worker",
        ["worker_pool_id", "last_heartbeat_time"],
        unique=False,
    )

    op.create_table(
        "worker_pool_queue",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_paused", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "worker_pool_id", prefect.server.utilities.database.UUID(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["worker_pool_id"],
            ["worker_pool.id"],
            name=op.f("fk_worker_pool_queue__worker_pool_id__worker_pool"),
            ondelete="cascade",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker_pool_queue")),
        sa.UniqueConstraint(
            "worker_pool_id",
            "name",
            name=op.f("uq_worker_pool_queue__worker_pool_id_name"),
        ),
    )
    op.create_index(
        op.f("ix_worker_pool_queue__updated"),
        "worker_pool_queue",
        ["updated"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_pool_queue__worker_pool_id_priority"),
        "worker_pool_queue",
        ["worker_pool_id", "priority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_worker_pool_queue__worker_pool_id"),
        "worker_pool_queue",
        ["worker_pool_id"],
        unique=False,
    )

    with op.batch_alter_table("worker_pool", schema=None) as batch_op:
        batch_op.create_foreign_key(
            batch_op.f("fk_worker_pool__default_queue_id__worker_pool_queue"),
            "worker_pool_queue",
            ["default_queue_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "worker_pool_queue_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_deployment__worker_pool_queue_id"),
            ["worker_pool_queue_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_deployment__worker_pool_queue_id__worker_pool_queue"),
            "worker_pool_queue",
            ["worker_pool_queue_id"],
            ["id"],
            ondelete="SET NULL",
        )
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "worker_pool_queue_id",
                prefect.server.utilities.database.UUID(),
                nullable=True,
            )
        )
        batch_op.create_index(
            batch_op.f("ix_flow_run__worker_pool_queue_id"),
            ["worker_pool_queue_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_flow_run__worker_pool_queue_id__worker_pool_queue"),
            "worker_pool_queue",
            ["worker_pool_queue_id"],
            ["id"],
            ondelete="SET NULL",
        )
