# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Add trigger to update runs when states are inserted

Revision ID: 8666a0ceb70e
Revises: aa594a91210c
Create Date: 2020-03-18 13:13:10.016540

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "8666a0ceb70e"
down_revision = "aa594a91210c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """

        -- trigger to update flow runs when flow run states are inserted

        CREATE FUNCTION update_flow_run_with_latest_state() RETURNS TRIGGER AS $$
            BEGIN
                UPDATE flow_run
                SET
                    version = new_latest_state.version,
                    state_id = new_latest_state.id,

                    -- below are fields that we only include for backwards-compatibility
                    state=new_latest_state.state,
                    serialized_state=new_latest_state.serialized_state,
                    state_start_time=new_latest_state.start_time,
                    state_timestamp=new_latest_state.timestamp,
                    state_message=new_latest_state.message,
                    state_result=new_latest_state.result
                FROM
                    -- only select the latest row
                    (
                        SELECT DISTINCT ON (flow_run_id)
                            id,
                            version,
                            flow_run_id,
                            state,
                            serialized_state,
                            start_time,
                            timestamp,
                            message,
                            result
                        FROM new_state
                        ORDER BY flow_run_id, version DESC, timestamp DESC
                    ) AS new_latest_state
                WHERE
                    new_latest_state.flow_run_id = flow_run.id
                    AND (
                        flow_run.version IS NULL
                        OR (
                            new_latest_state.version >= COALESCE(flow_run.version, -1)
                            AND new_latest_state.timestamp > COALESCE(flow_run.state_timestamp, '2000-01-01')));

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;



        -- trigger to update task runs when task run states are inserted

        CREATE FUNCTION update_task_run_with_latest_state() RETURNS TRIGGER AS $$
            BEGIN
                UPDATE task_run
                SET
                    version = new_latest_state.version,
                    state_id = new_latest_state.id,

                    -- below are fields that we only include for backwards-compatibility
                    state=new_latest_state.state,
                    serialized_state=new_latest_state.serialized_state,
                    state_start_time=new_latest_state.start_time,
                    state_timestamp=new_latest_state.timestamp,
                    state_message=new_latest_state.message,
                    state_result=new_latest_state.result
                FROM
                    -- only select the latest row
                    (
                        SELECT DISTINCT ON (task_run_id)
                            id,
                            version,
                            task_run_id,
                            state,
                            serialized_state,
                            start_time,
                            timestamp,
                            message,
                            result
                        FROM new_state
                        ORDER BY task_run_id, version DESC, timestamp DESC
                    ) AS new_latest_state
                WHERE
                    new_latest_state.task_run_id = task_run.id
                    AND (
                        task_run.version IS NULL
                        OR (
                            new_latest_state.version >= COALESCE(task_run.version, -1)
                            AND new_latest_state.timestamp > COALESCE(task_run.state_timestamp, '2000-01-01')));

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

        CREATE TRIGGER update_flow_run_after_inserting_state
        AFTER INSERT ON flow_run_state
        REFERENCING NEW TABLE AS new_state
        FOR EACH STATEMENT
        EXECUTE PROCEDURE update_flow_run_with_latest_state();

        CREATE TRIGGER update_task_run_after_inserting_state
        AFTER INSERT ON task_run_state
        REFERENCING NEW TABLE AS new_state
        FOR EACH STATEMENT
        EXECUTE PROCEDURE update_task_run_with_latest_state();

        """
    )


def downgrade():
    op.execute(
        """
        DROP FUNCTION update_flow_run_with_latest_state CASCADE;
        DROP FUNCTION update_task_run_with_latest_state CASCADE;

        """
    )
