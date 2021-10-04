INSERT INTO flow (name)
SELECT
    'flow' || i
FROM
    generate_series(1, 20) i;

INSERT INTO flow_run (flow_id)
SELECT
    flow.id
FROM
    generate_series(1, 25) i
    CROSS JOIN flow;

INSERT INTO task_run (flow_run_id, task_key, dynamic_key)
SELECT
    flow_run.id,
    mod(i, 5),
    i
FROM
    generate_series(1, 100) i
    CROSS JOIN flow_run;

INSERT INTO flow_run_state (flow_run_id, TYPE, name, timestamp, state_details)
WITH states (TYPE, name, timestamp, state_details)
AS (
        VALUES ('SCHEDULED'::state_type, 'Scheduled', CURRENT_TIMESTAMP - INTERVAL '1 HOUR', ('{"scheduled_time":"' || CURRENT_TIMESTAMP - INTERVAL '1 HOUR' || '"}')::jsonb), ('PENDING', 'Pending', CURRENT_TIMESTAMP - INTERVAL '59 minutes', '{}'), ('RUNNING', 'Running', CURRENT_TIMESTAMP - INTERVAL '58 minutes', '{}'), ('COMPLETED', 'Completed', CURRENT_TIMESTAMP - INTERVAL '5 minutes', '{}'))
        SELECT
            flow_run.id,
            states.*
        FROM
            states
        CROSS JOIN (
            SELECT
                *
            FROM
                flow_run
            ORDER BY
                id
            LIMIT 500) flow_run;

INSERT INTO flow_run_state (flow_run_id, TYPE, name, timestamp, state_details)
WITH states (TYPE, name, timestamp, state_details)
AS (
        VALUES ('SCHEDULED'::state_type, 'Scheduled', CURRENT_TIMESTAMP - INTERVAL '1 HOUR', ('{"scheduled_time":"' || CURRENT_TIMESTAMP + INTERVAL '1 HOUR' || '"}')::jsonb))
        SELECT
            flow_run.id,
            states.*
        FROM
            states
        CROSS JOIN (
            SELECT
                *
            FROM
                flow_run
            ORDER BY
                id OFFSET 500) flow_run;

INSERT INTO task_run_state (task_run_id, TYPE, name, timestamp, state_details)
WITH states (TYPE, name, timestamp, state_details)
AS (
        VALUES ('SCHEDULED'::state_type, 'Scheduled', CURRENT_TIMESTAMP - INTERVAL '1 HOUR', ('{"scheduled_time":"' || CURRENT_TIMESTAMP - INTERVAL '1 HOUR' || '"}')::jsonb), ('PENDING', 'Pending', CURRENT_TIMESTAMP - INTERVAL '59 minutes', '{}'), ('RUNNING', 'Running', CURRENT_TIMESTAMP - INTERVAL '58 minutes', '{}'), ('COMPLETED', 'Completed', CURRENT_TIMESTAMP - INTERVAL '5 minutes', '{}'))
        SELECT
            task_run.id,
            states.*
        FROM
            states
        CROSS JOIN (
            SELECT
                *
            FROM
                task_run
            ORDER BY
                id
            LIMIT 25000) task_run;

INSERT INTO task_run_state (task_run_id, TYPE, name, timestamp, state_details)
WITH states (TYPE, name, timestamp, state_details)
AS (
        VALUES ('SCHEDULED'::state_type, 'Scheduled', CURRENT_TIMESTAMP - INTERVAL '1 HOUR', ('{"scheduled_time":"' || CURRENT_TIMESTAMP - INTERVAL '1 HOUR' || '"}')::jsonb), ('PENDING', 'Pending', CURRENT_TIMESTAMP - INTERVAL '59 minutes', '{}'), ('RUNNING', 'Running', CURRENT_TIMESTAMP - INTERVAL '58 minutes', '{}'), ('SCHEDULED', 'AwaitingRetry', CURRENT_TIMESTAMP - INTERVAL '5 minutes', ('{"scheduled_time":"' || CURRENT_TIMESTAMP - INTERVAL '3 MINUTES' || '"}')::jsonb), ('RUNNING', 'Retrying', CURRENT_TIMESTAMP - INTERVAL '2 minutes', '{}'), ('FAILED', 'Failed', CURRENT_TIMESTAMP, '{}'))
        SELECT
            task_run.id,
            states.*
        FROM
            states
        CROSS JOIN (
            SELECT
                *
            FROM
                task_run
            ORDER BY
                id OFFSET 25000
            LIMIT 15000) task_run;

INSERT INTO task_run_state (task_run_id, TYPE, name, timestamp, state_details)
WITH states (TYPE, name, timestamp, state_details)
AS (
        VALUES ('SCHEDULED'::state_type, 'Scheduled', CURRENT_TIMESTAMP - INTERVAL '1 HOUR', ('{"scheduled_time":"' || CURRENT_TIMESTAMP + INTERVAL '1 HOUR' || '"}')::jsonb))
        SELECT
            task_run.id,
            states.*
        FROM
            states
        CROSS JOIN (
            SELECT
                *
            FROM
                task_run
            ORDER BY
                id OFFSET 40000) task_run;



UPDATE flow_run
SET state_id = (
    SELECT id
    FROM flow_run_state
    WHERE flow_run_id = flow_run.id
    ORDER BY timestamp DESC
    LIMIT 1
);

UPDATE task_run
SET state_id = (
    SELECT id
    FROM task_run_state
    WHERE task_run_id = task_run.id
    ORDER BY timestamp DESC
    LIMIT 1
);
