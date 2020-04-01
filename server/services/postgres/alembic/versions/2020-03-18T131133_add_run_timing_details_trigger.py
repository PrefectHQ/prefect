# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Add run timing details trigger

Revision ID: aa594a91210c
Revises: 6c48e68b5e97
Create Date: 2020-03-18 13:11:33.332038

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "aa594a91210c"
down_revision = "6c48e68b5e97"
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """
        -- trigger to update flow runs when flow run states are inserted
        -- note: these triggers consider the minimum and maximum timestamps from all valid
        -- RUNNING states and the states that immediately follow them.

        CREATE FUNCTION update_flow_run_with_timing_details() RETURNS TRIGGER AS $$
            BEGIN
                UPDATE flow_run
                SET
                    start_time = run_details.start_time,
                    end_time = run_details.end_time,
                    duration = run_details.duration
                FROM (
                    SELECT
                        flow_run_id,
                        min(start_timestamp) AS start_time,
                        max(end_timestamp) AS end_time,
                        max(end_timestamp) - min(start_timestamp) AS duration
                    FROM (
                        SELECT
                            id,
                            flow_run_id,
                            state,
                            timestamp AS start_timestamp,

                            -- order by version AND timestamp to break ties for old states that don't have versions
                            LEAD(timestamp) OVER (PARTITION BY flow_run_id ORDER BY version, timestamp) AS end_timestamp

                        FROM
                            flow_run_state
                        WHERE flow_run_id in (SELECT flow_run_id FROM new_state)
                        ) ts
                    WHERE
                        state = 'Running'
                    GROUP BY flow_run_id
                    ORDER BY flow_run_id
                ) run_details
                WHERE run_details.flow_run_id = flow_run.id;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;



        -- trigger to update task runs when task run states are inserted
        -- note: these triggers consider the minimum and maximum timestamps from all valid
        -- RUNNING states and the states that immediately follow them.

        CREATE FUNCTION update_task_run_with_timing_details() RETURNS TRIGGER AS $$
            BEGIN
                UPDATE task_run
                SET
                    start_time = run_details.start_time,
                    end_time = run_details.end_time,
                    duration = run_details.duration,
                    run_count = run_details.run_count
                FROM (
                    SELECT
                        task_run_id,

                        -- start time, end time, and duartion are all computed from running states
                        min(start_timestamp) FILTER (WHERE state = 'Running') AS start_time,
                        max(end_timestamp) FILTER (WHERE state = 'Running') AS end_time,
                        max(end_timestamp) FILTER (WHERE state = 'Running') - min(start_timestamp) FILTER (WHERE state = 'Running') AS duration,

                        -- run count needs to subtract looped states
                        count(*) FILTER (WHERE state = 'Running') - count(*) FILTER (WHERE state = 'Looped') AS run_count
                    FROM (
                        SELECT
                            id,
                            task_run_id,
                            state,
                            timestamp AS start_timestamp,

                            -- order by version AND timestamp to break ties for old states that don't have versions
                            LEAD(timestamp) OVER (PARTITION BY task_run_id ORDER BY version, timestamp) AS end_timestamp

                        FROM
                            task_run_state
                        WHERE task_run_id in (SELECT task_run_id FROM new_state)
                        ) ts
                    WHERE
                        state in ('Running', 'Looped')
                    GROUP BY task_run_id
                    ORDER BY task_run_id
                ) run_details
                WHERE run_details.task_run_id = task_run.id;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

        CREATE TRIGGER update_flow_run_timing_details_after_inserting_state
        AFTER INSERT ON flow_run_state
        REFERENCING NEW TABLE AS new_state
        FOR EACH STATEMENT
        EXECUTE PROCEDURE update_flow_run_with_timing_details();

        CREATE TRIGGER update_task_run_timing_details_after_inserting_state
        AFTER INSERT ON task_run_state
        REFERENCING NEW TABLE AS new_state
        FOR EACH STATEMENT
        EXECUTE PROCEDURE update_task_run_with_timing_details();

        """
    )


def downgrade():

    op.execute(
        """
        DROP FUNCTION update_flow_run_with_timing_details CASCADE;
        DROP FUNCTION update_task_run_with_timing_details CASCADE;
        """
    )
