# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Add task run trigger

Revision ID: 6c48e68b5e97
Revises: 7ff37edbf446
Create Date: 2020-03-18 13:10:36.269070

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "6c48e68b5e97"
down_revision = "7ff37edbf446"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE FUNCTION insert_task_runs_after_flow_run_insert() RETURNS TRIGGER AS $$
            BEGIN
                -- create task runs for each of the tasks in the new flow run's
                -- flow
                INSERT INTO task_run (flow_run_id, task_id, cache_key, map_index)
                SELECT NEW.id, task.id, task.cache_key, -1
                FROM task
                WHERE task.flow_id = NEW.flow_id;

                -- create corresponding states for each of the new task runs
                INSERT INTO task_run_state(task_run_id, state, message, serialized_state)
                SELECT task_run.id, 'Pending', 'Task run created', '{"type": "Pending", "message": "Task run created"}'
                FROM task_run
                WHERE task_run.flow_run_id = NEW.id;
            RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

        CREATE TRIGGER insert_task_runs_after_flow_run_insert
        AFTER INSERT
        ON flow_run
        FOR EACH ROW
        EXECUTE PROCEDURE insert_task_runs_after_flow_run_insert();
    """
    )


def downgrade():
    op.execute("DROP FUNCTION insert_task_runs_after_flow_run_insert CASCADE;")
