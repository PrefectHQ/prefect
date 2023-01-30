"""Expand work queue table

Revision ID: b9bda9f142f1
Revises: bb38729c471a
Create Date: 2023-01-25 11:43:48.160070

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "b9bda9f142f1"
down_revision = "f92143d30c27"
branch_labels = None
depends_on = None

# Note: Downgrade for this migration is destructive if additional work pools have been created.


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
                "work_pool_id", prefect.orion.utilities.database.UUID(), nullable=True
            )
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_work_queue__work_pool_id__work_pool"),
            "work_pool",
            ["work_pool_id"],
            ["id"],
            ondelete="cascade",
        )
        batch_op.drop_constraint("uq_work_queue__name")
        batch_op.create_unique_constraint(
            op.f("uq_work_queue__work_pool_id_name"), ["work_pool_id", "name"]
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
        batch_op.alter_column("type", nullable=False)

    # Create default agent work pool and associate all existing queues with it
    connection = op.get_bind()

    connection.execute(
        sa.text(
            "INSERT INTO work_pool (name, type) VALUES ('default-agent-pool', 'prefect-agent')"
        )
    )

    default_pool_id = connection.execute(
        sa.text("SELECT id FROM work_pool WHERE name = 'default-agent-pool'")
    ).fetchone()[0]

    default_queue = connection.execute(
        sa.text("SELECT id FROM work_queue WHERE name = 'default'")
    ).fetchone()

    if not default_queue:
        connection.execute(
            sa.text(
                f"INSERT INTO work_queue (name, work_pool_id) VALUES ('default', :default_pool_id)"
            ).params({"default_pool_id": default_pool_id}),
        )

    connection.execute(
        sa.text(
            "UPDATE work_queue SET work_pool_id = :default_pool_id WHERE work_pool_id IS NULL"
        ).params({"default_pool_id": default_pool_id}),
    )

    default_queue_id = connection.execute(
        sa.text(
            "SELECT id FROM work_queue WHERE name = 'default' and work_pool_id = :default_pool_id"
        ).params({"default_pool_id": default_pool_id}),
    ).fetchone()[0]

    connection.execute(
        sa.text(
            "UPDATE work_pool SET default_queue_id = :default_queue_id WHERE id = :default_pool_id"
        ).params(
            {"default_pool_id": default_pool_id, "default_queue_id": default_queue_id}
        ),
    )

    # Set priority on all queues and update flow runs and deployments
    queue_rows = connection.execute(
        sa.text(
            "SELECT id, name FROM work_queue WHERE work_pool_id = :default_pool_id"
        ).params({"default_pool_id": default_pool_id}),
    ).fetchall()

    with op.get_context().autocommit_block():
        for enumeration, row in enumerate(queue_rows):
            connection.execute(
                sa.text(
                    "UPDATE work_queue SET priority = :priority WHERE id = :id"
                ).params({"priority": enumeration + 1, "id": row[0]}),
            )

            batch_size = 250

            while True:
                result = connection.execute(
                    sa.text(
                        """
                        UPDATE flow_run 
                        SET work_queue_id=:id 
                        WHERE flow_run.id in (
                            SELECT id 
                            FROM flow_run 
                            WHERE flow_run.work_queue_id IS NULL and flow_run.work_queue_name=:name 
                            LIMIT :batch_size
                        )
                        """
                    ).params({"id": row[0], "name": row[1], "batch_size": batch_size}),
                )
                if result.rowcount <= 0:
                    break

            while True:
                result = connection.execute(
                    sa.text(
                        """
                        UPDATE deployment 
                        SET work_queue_id=:id 
                        WHERE deployment.id in (
                            SELECT id 
                            FROM deployment 
                            WHERE deployment.work_queue_id IS NULL and deployment.work_queue_name=:name 
                            LIMIT :batch_size
                        )
                        """
                    ).params({"id": row[0], "name": row[1], "batch_size": batch_size}),
                )
                if result.rowcount <= 0:
                    break

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.alter_column("work_pool_id", nullable=False)

    op.execute("PRAGMA foreign_keys=ON")


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    connection = op.get_bind()

    # Delete all non-default queues and pools
    default_pool_id_result = connection.execute(
        sa.text("SELECT id FROM work_pool WHERE name = 'default-agent-pool'")
    ).fetchone()
    if default_pool_id_result:
        default_pool_id = default_pool_id_result[0]
        connection.execute(
            sa.text(
                "DELETE FROM work_queue WHERE work_pool_id != :default_pool_id"
            ).params({"default_pool_id": default_pool_id})
        )

    connection.execute(
        sa.text("DELETE FROM work_pool WHERE name != 'default-agent-pool'")
    )

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_index("ix_work_queue__work_pool_id_priority")
        batch_op.drop_index("ix_work_queue__work_pool_id")
        batch_op.drop_constraint("uq_work_queue__work_pool_id_name")
        batch_op.create_unique_constraint("uq_work_queue__name", ["name"])
        batch_op.drop_constraint("fk_work_queue__work_pool_id__work_pool")
        batch_op.drop_column("work_pool_id")
        batch_op.drop_column("priority")

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

    connection.execute(sa.text("DELETE FROM work_pool"))

    op.create_table(
        "work_pool_queue",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text(
                "(\n    (\n        lower(hex(randomblob(4)))\n        || '-'\n        || lower(hex(randomblob(2)))\n        || '-4'\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || substr('89ab',abs(random()) % 4 + 1, 1)\n        || substr(lower(hex(randomblob(2))),2)\n        || '-'\n        || lower(hex(randomblob(6)))\n    )\n    )"
            ),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_paused", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "work_pool_id", prefect.orion.utilities.database.UUID(), nullable=False
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
        batch_op.alter_column("type", nullable=True)

    with op.batch_alter_table("deployment", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "work_pool_queue_id",
                prefect.orion.utilities.database.UUID(),
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
                prefect.orion.utilities.database.UUID(),
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
