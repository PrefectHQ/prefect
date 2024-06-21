"""Migrates state data to the artifact table

Revision ID: 2882cd2df465
Revises: 2882cd2df464
Create Date: 2023-01-26 04:55:01.358638

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2882cd2df465"
down_revision = "2882cd2df464"
branch_labels = None
depends_on = None


def upgrade():
    ### START DATA MIGRATION

    # insert nontrivial task run state results into the artifact table
    def update_task_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (task_run_state_id, task_run_id, data)
            SELECT id, task_run_id, data
            FROM task_run_state
            WHERE has_data IS TRUE
            ORDER BY id
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the task run state table
    def update_task_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE task_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE task_run_state.id = task_run_state_id)
            WHERE task_run_state.id in (SELECT id FROM task_run_state WHERE (has_data IS TRUE) AND (result_artifact_id IS NULL) LIMIT {batch_size});
        """

    # insert nontrivial flow run state results into the artifact table
    def update_flow_run_artifact_data_in_batches(batch_size, offset):
        return f"""
            INSERT INTO artifact (flow_run_state_id, flow_run_id, data)
            SELECT id, flow_run_id, data
            FROM flow_run_state
            WHERE has_data IS TRUE
            ORDER BY id
            LIMIT {batch_size} OFFSET {offset};
        """

    # backpopulate the result artifact id on the flow run state table
    def update_flow_run_state_from_artifact_id_in_batches(batch_size, offset):
        return f"""
            UPDATE flow_run_state
            SET result_artifact_id = (SELECT id FROM artifact WHERE flow_run_state.id = flow_run_state_id)
            WHERE flow_run_state.id in (SELECT id FROM flow_run_state WHERE (has_data IS TRUE) AND (result_artifact_id IS NULL) LIMIT {batch_size});
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


def downgrade():
    def nullify_artifact_ref_from_flow_run_state_in_batches(batch_size):
        return f"""
            UPDATE flow_run_state
            SET result_artifact_id = NULL
            WHERE flow_run_state.id in (SELECT id FROM flow_run_state WHERE result_artifact_id IS NOT NULL LIMIT {batch_size});
        """

    def nullify_artifact_ref_from_task_run_state_in_batches(batch_size):
        return f"""
            UPDATE task_run_state
            SET result_artifact_id = NULL
            WHERE task_run_state.id in (SELECT id FROM task_run_state WHERE result_artifact_id IS NOT NULL LIMIT {batch_size});
        """

    def delete_artifacts_in_batches(batch_size):
        return f"""
            DELETE FROM artifact
            WHERE artifact.id IN (SELECT id FROM artifact LIMIT {batch_size});
        """

    data_migration_queries = [
        delete_artifacts_in_batches,
        nullify_artifact_ref_from_flow_run_state_in_batches,
        nullify_artifact_ref_from_task_run_state_in_batches,
    ]

    with op.get_context().autocommit_block():
        conn = op.get_bind()
        for query in data_migration_queries:
            batch_size = 500

            while True:
                # execute until we've updated task_run_state_id and artifact_data
                # autocommit mode will commit each time `execute` is called
                sql_stmt = sa.text(query(batch_size))
                result = conn.execute(sql_stmt)

                if result.rowcount <= 0:
                    break
