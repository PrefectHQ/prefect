"""Adds a helper index for the artifact data migration

Revision ID: f92143d30c25
Revises: f92143d30c24
Create Date: 2023-01-12 00:00:43.488367

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f92143d30c25"
down_revision = "f92143d30c24"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("has_data", sa.Boolean))
        batch_op.create_index(
            batch_op.f("ix_flow_run_state__has_data"),
            ["has_data"],
            unique=False,
        )

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("has_data", sa.Boolean))
        batch_op.create_index(
            batch_op.f("ix_task_run_state__has_data"),
            ["has_data"],
            unique=False,
        )

    def populate_flow_has_data_in_batches(batch_size):
        return f"""
            UPDATE flow_run_state
            SET has_data = (data IS NOT NULL AND data IS NOT 'null')
            WHERE flow_run_state.id in (SELECT id FROM flow_run_state WHERE (has_data IS NULL) LIMIT {batch_size});
        """

    def populate_task_has_data_in_batches(batch_size):
        return f"""
            UPDATE task_run_state
            SET has_data = (data IS NOT NULL AND data IS NOT 'null')
            WHERE task_run_state.id in (SELECT id FROM task_run_state WHERE (has_data IS NULL) LIMIT {batch_size});
        """

    migration_statements = [
        populate_flow_has_data_in_batches,
        populate_task_has_data_in_batches,
    ]

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        for query in migration_statements:
            batch_size = 500

            while True:
                # execute until we've updated task_run_state_id and artifact_data
                # autocommit mode will commit each time `execute` is called
                sql_stmt = sa.text(query(batch_size))
                result = conn.execute(sql_stmt)

                if result.rowcount < batch_size:
                    break


def downgrade():
    op.execute("PRAGMA foreign_keys=OFF")

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_task_run_state__has_data"))
        batch_op.drop_column("has_data")

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_flow_run_state__has_data"))
        batch_op.drop_column("has_data")
