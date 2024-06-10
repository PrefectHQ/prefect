"""Rename Worker Pools to Work Pools

Revision ID: bb38729c471a
Revises: fe77ad0dda06
Create Date: 2023-01-08 17:53:27.444733

"""

import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "bb38729c471a"
down_revision = "fe77ad0dda06"
branch_labels = None
depends_on = None


### NOTE ###
# This upgrade is destructive for anyone who has created a worker
###


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    ## first we reset to a clean, no-worker slate
    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_index("ix_deployment__worker_pool_queue_id")
        batch_op.drop_constraint(
            "fk_deployment__worker_pool_queue_id__worker_pool_queue"
        )
        batch_op.drop_column("worker_pool_queue_id")
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__worker_pool_queue_id")
        batch_op.drop_constraint("fk_flow_run__worker_pool_queue_id__worker_pool_queue")
        batch_op.drop_column("worker_pool_queue_id")

    with op.batch_alter_table("worker_pool", schema=None) as batch_op:
        batch_op.drop_constraint("fk_worker_pool__default_queue_id__worker_pool_queue")
    op.drop_table("worker_pool_queue")
    op.drop_table("worker")
    op.drop_table("worker_pool")

    ## then we recreate all tables and relationships
    op.create_table(
        "work_pool",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
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
    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_work_pool__updated"), ["updated"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_work_pool__type"), ["type"], unique=False)

    op.create_table(
        "worker",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "last_heartbeat_time",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
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
    with op.batch_alter_table("worker", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_worker__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_worker__work_pool_id_last_heartbeat_time"),
            ["work_pool_id", "last_heartbeat_time"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_worker__work_pool_id"),
            ["work_pool_id"],
            unique=False,
        )

    op.create_table(
        "work_pool_queue",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
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
    with op.batch_alter_table("work_pool_queue", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_work_pool_queue__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_work_pool_queue__work_pool_id_priority"),
            ["work_pool_id", "priority"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_work_pool_queue__work_pool_id"),
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

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.drop_index("ix_deployment__work_pool_queue_id")
        batch_op.drop_constraint("fk_deployment__work_pool_queue_id__work_pool_queue")
        batch_op.drop_column("work_pool_queue_id")
    with op.batch_alter_table("flow_run", schema=None) as batch_op:
        batch_op.drop_index("ix_flow_run__work_pool_queue_id")
        batch_op.drop_constraint("fk_flow_run__work_pool_queue_id__work_pool_queue")
        batch_op.drop_column("work_pool_queue_id")

    with op.batch_alter_table("work_pool", schema=None) as batch_op:
        batch_op.drop_constraint("fk_work_pool__default_queue_id__work_pool_queue")
    op.drop_table("work_pool_queue")
    op.drop_table("worker")
    op.drop_table("work_pool")

    op.create_table(
        "worker_pool",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
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
    with op.batch_alter_table("worker_pool", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_worker_pool__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_worker_pool__type"), ["type"], unique=False
        )

    op.create_table(
        "worker",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "last_heartbeat_time",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
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
    with op.batch_alter_table("worker", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_worker__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_worker__worker_pool_id_last_heartbeat_time"),
            ["worker_pool_id", "last_heartbeat_time"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_worker__worker_pool_id"),
            ["worker_pool_id"],
            unique=False,
        )

    op.create_table(
        "worker_pool_queue",
        sa.Column(
            "id",
            prefect.server.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n       "
                " || lower(hex(randomblob(2)))\n        || '-4'\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " substr('89ab',abs(random()) % 4 + 1, 1)\n        ||"
                " substr(lower(hex(randomblob(2))),2)\n        || '-'\n        ||"
                " lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.server.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
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
    with op.batch_alter_table("worker_pool_queue", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_worker_pool_queue__updated"), ["updated"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_worker_pool_queue__worker_pool_id_priority"),
            ["worker_pool_id", "priority"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_worker_pool_queue__worker_pool_id"),
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
    op.execute("PRAGMA foreign_keys=ON")
