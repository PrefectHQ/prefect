"""Work queue data migration

Revision ID: 1678f2fb8b33
Revises: b9bda9f142f1
Create Date: 2023-01-31 10:54:42.747849

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "1678f2fb8b33"
down_revision = "b9bda9f142f1"
branch_labels = None
depends_on = None


def upgrade():
    # Create temporary indexes for migration
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_flow_run__work_queue_id_work_queue_name ON"
        " flow_run (work_queue_id, work_queue_name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_deployment__work_queue_id_work_queue_name ON"
        " deployment (work_queue_id, work_queue_name)"
    )

    # Create default agent work pool and associate all existing queues with it
    connection = op.get_bind()

    n_work_queues_without_a_work_pool = connection.execute(
        sa.text("SELECT COUNT(*) FROM work_queue WHERE work_pool_id IS NULL")
    ).fetchone()[0]

    if n_work_queues_without_a_work_pool > 0:
        connection.execute(
            sa.text(
                "INSERT INTO work_pool (name, type) VALUES ('default-agent-pool',"
                " 'prefect-agent')"
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
                    "INSERT INTO work_queue (name, work_pool_id) VALUES ('default',"
                    " :default_pool_id)"
                ).params({"default_pool_id": default_pool_id}),
            )

        connection.execute(
            sa.text(
                "UPDATE work_queue SET work_pool_id = :default_pool_id WHERE work_pool_id"
                " IS NULL"
            ).params({"default_pool_id": default_pool_id}),
        )

        default_queue_id = connection.execute(
            sa.text(
                "SELECT id FROM work_queue WHERE name = 'default' and work_pool_id ="
                " :default_pool_id"
            ).params({"default_pool_id": default_pool_id}),
        ).fetchone()[0]

        connection.execute(
            sa.text(
                "UPDATE work_pool SET default_queue_id = :default_queue_id WHERE id ="
                " :default_pool_id"
            ).params(
                {
                    "default_pool_id": default_pool_id,
                    "default_queue_id": default_queue_id,
                }
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
                        ).params(
                            {"id": row[0], "name": row[1], "batch_size": batch_size}
                        ),
                    )
                    if result.rowcount <= batch_size:
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
                        ).params(
                            {"id": row[0], "name": row[1], "batch_size": batch_size}
                        ),
                    )
                    if result.rowcount <= batch_size:
                        break

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_constraint("uq_work_queue__name")
        batch_op.create_unique_constraint(
            op.f("uq_work_queue__work_pool_id_name"), ["work_pool_id", "name"]
        )
        batch_op.alter_column("work_pool_id", nullable=False)

    op.execute("DROP INDEX IF EXISTS ix_flow_run__work_queue_id_work_queue_name")
    op.execute("DROP INDEX IF EXISTS ix_deployment__work_queue_id_work_queue_name")


def downgrade():
    connection = op.get_bind()
    # Create temporary indexes for migration
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_flow_run__work_queue_id_work_queue_name ON"
        " flow_run (work_queue_id, work_queue_name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_deployment__work_queue_id_work_queue_name ON"
        " deployment (work_queue_id, work_queue_name)"
    )

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.alter_column("work_pool_id", nullable=True)

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
    queue_rows = connection.execute(
        sa.text("SELECT id, name FROM work_queue"),
    ).fetchall()

    with op.get_context().autocommit_block():
        for row in queue_rows:
            batch_size = 250

            while True:
                result = connection.execute(
                    sa.text(
                        """
                        UPDATE flow_run 
                        SET work_queue_id=NULL 
                        WHERE flow_run.id in (
                            SELECT id 
                            FROM flow_run 
                            WHERE flow_run.work_queue_id IS NOT NULL and flow_run.work_queue_id=:id 
                            LIMIT :batch_size
                        )
                        """
                    ).params({"id": row[0], "batch_size": batch_size}),
                )
                if result.rowcount <= batch_size:
                    break

            while True:
                result = connection.execute(
                    sa.text(
                        """
                        UPDATE deployment 
                        SET work_queue_id=NULL 
                        WHERE deployment.id in (
                            SELECT id 
                            FROM deployment 
                            WHERE deployment.work_queue_id IS NOT NULL and deployment.work_queue_id=:id
                            LIMIT :batch_size
                        )
                        """
                    ).params({"id": row[0], "batch_size": batch_size}),
                )
                if result.rowcount <= batch_size:
                    break

    connection.execute(sa.text("UPDATE work_queue SET work_pool_id = NULL"))

    connection.execute(sa.text("DELETE FROM work_pool"))

    with op.batch_alter_table("work_queue", schema=None) as batch_op:
        batch_op.drop_constraint("uq_work_queue__work_pool_id_name")
        batch_op.create_unique_constraint("uq_work_queue__name", ["name"])

    op.execute("DROP INDEX IF EXISTS ix_flow_run__work_queue_id_work_queue_name")
    op.execute("DROP INDEX IF EXISTS ix_deployment__work_queue_id_work_queue_name")
