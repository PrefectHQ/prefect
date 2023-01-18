"""Implements the artifact table and migrates run results

Revision ID: 2882cd2df463
Revises: d481d5058a19
Create Date: 2023-01-13 04:55:00.358638

"""
import sqlalchemy as sa
from alembic import op

import prefect

# revision identifiers, used by Alembic.
revision = "2882cd2df463"
down_revision = "d481d5058a19"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "artifact",
        sa.Column(
            "id",
            prefect.orion.utilities.database.UUID(),
            server_default=sa.text("(GEN_RANDOM_UUID())"),
            nullable=False,
        ),
        sa.Column(
            "created",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated",
            prefect.orion.utilities.database.Timestamp(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=True),
        sa.Column("artifact_type", sa.String(), nullable=True),
        sa.Column("artifact_data", sa.JSON(), nullable=True),
        sa.Column("artifact_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "task_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "task_run_state_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.Column(
            "flow_run_state_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_id"],
            ["flow_run.id"],
            name=op.f("fk_artifact__flow_run_id__flow_run"),
        ),
        sa.ForeignKeyConstraint(
            ["flow_run_state_id"],
            ["flow_run_state.id"],
            name=op.f("fk_artifact__flow_run_state_id__flow_run_state"),
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            ["task_run.id"],
            name=op.f("fk_artifact__task_run_id__task_run"),
        ),
        sa.ForeignKeyConstraint(
            ["task_run_state_id"],
            ["task_run_state.id"],
            name=op.f("fk_artifact__task_run_state_id__task_run_state"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact")),
    )
    op.create_index(
        op.f("ix_artifact__flow_run_id"), "artifact", ["flow_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_artifact__flow_run_state_id"),
        "artifact",
        ["flow_run_state_id"],
        unique=False,
    )
    op.create_index(op.f("ix_artifact__key"), "artifact", ["key"], unique=True)
    op.create_index(
        op.f("ix_artifact__task_run_id"), "artifact", ["task_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_artifact__task_run_state_id"),
        "artifact",
        ["task_run_state_id"],
        unique=False,
    )
    op.create_index(op.f("ix_artifact__updated"), "artifact", ["updated"], unique=False)

    op.add_column(
        "flow_run_state",
        sa.Column(
            "result_artifact_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_flow_run_state__result_artifact_id"),
        "flow_run_state",
        ["result_artifact_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_flow_run_state__result_artifact_id__artifact"),
        "flow_run_state",
        "artifact",
        ["result_artifact_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )
    op.add_column(
        "task_run_state",
        sa.Column(
            "result_artifact_id", prefect.orion.utilities.database.UUID(), nullable=True
        ),
    )
    op.create_index(
        op.f("ix_task_run_state__result_artifact_id"),
        "task_run_state",
        ["result_artifact_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_task_run_state__result_artifact_id__artifact"),
        "task_run_state",
        "artifact",
        ["result_artifact_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")

    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.alter_column("data", new_column_name="_data")

    ### START DATA MIGRATION

    # insert nontrivial task run state results into the artifact table
    def update_task_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (task_run_state_id, task_run_id, artifact_data)
            SELECT id, task_run_id, _data
            FROM task_run_state
            WHERE _data != 'null' AND _data IS NOT NULL
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the task run state table
    def update_task_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE task_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE task_run_state.id = task_run_state_id)
            WHERE task_run_state.id in (SELECT id FROM task_run_state WHERE (_data != 'null' AND _data IS NOT NULL) AND (result_artifact_id IS NULL) LIMIT {batch_size});
        """

    # insert nontrivial flow run state results into the artifact table
    def update_flow_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (flow_run_state_id, flow_run_id, artifact_data)
            SELECT id, flow_run_id, _data
            FROM flow_run_state
            WHERE _data != 'null' AND _data IS NOT NULL
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the flow run state table
    def update_flow_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE flow_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE flow_run_state.id = flow_run_state_id)
            WHERE flow_run_state.id in (SELECT id FROM flow_run_state WHERE (_data != 'null' AND _data IS NOT NULL) AND (result_artifact_id IS NULL) LIMIT {batch_size});
        """

    data_migration_queries = [
        update_task_run_artifact_data_in_batches,
        update_task_run_state_from_artifact_id_in_batches,
        update_flow_run_artifact_data_in_batches,
        update_flow_run_state_from_artifact_id_in_batches,
    ]

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        for query in data_migration_queries:

            batch_size = 500
            offset = 0

            while True:
                # execute until we've updated task_run_state_id and artifact_data
                # autocommit mode will commit each time `execute` is called
                sql_stmt = sa.text(query(batch_size, offset))
                result = conn.execute(sql_stmt)

                if result.rowcount <= 0:
                    break

                offset += batch_size

    ### END DATA MIGRATION

    # drop state id columns after data migration
    op.drop_index(op.f("ix_artifact__task_run_state_id"), table_name="artifact")
    op.drop_column("artifact", "task_run_state_id")
    op.drop_index(op.f("ix_artifact__flow_run_state_id"), table_name="artifact")
    op.drop_column("artifact", "flow_run_state_id")


def downgrade():
    with op.batch_alter_table("task_run_state", schema=None) as batch_op:
        batch_op.alter_column("_data", new_column_name="data")

    with op.batch_alter_table("flow_run_state", schema=None) as batch_op:
        batch_op.alter_column("_data", new_column_name="data")

    op.drop_constraint(
        op.f("fk_task_run_state__result_artifact_id__artifact"),
        "task_run_state",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_task_run_state__result_artifact_id"), table_name="task_run_state"
    )
    op.drop_column("task_run_state", "result_artifact_id")
    op.drop_constraint(
        op.f("fk_flow_run_state__result_artifact_id__artifact"),
        "flow_run_state",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_flow_run_state__result_artifact_id"), table_name="flow_run_state"
    )
    op.drop_column("flow_run_state", "result_artifact_id")

    op.drop_index(op.f("ix_artifact__updated"), table_name="artifact")
    op.drop_index(op.f("ix_artifact__task_run_id"), table_name="artifact")
    op.drop_index(op.f("ix_artifact__key"), table_name="artifact")
    op.drop_index(op.f("ix_artifact__flow_run_id"), table_name="artifact")
    op.drop_table("artifact")
