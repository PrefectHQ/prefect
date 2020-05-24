# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Initial migration

Revision ID: 7ff37edbf446
Revises: 2f249ccdcba7
Create Date: 2020-03-18 09:46:06.168069

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "7ff37edbf446"
down_revision = "2f249ccdcba7"
branch_labels = None
depends_on = None


def upgrade():

    op.execute(
        """ 
        -- Table Definition ----------------------------------------------

        CREATE TABLE flow (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created timestamp with time zone NOT NULL DEFAULT now(),
            version integer,
            name character varying NOT NULL,
            description character varying,
            environment jsonb,
            parameters jsonb DEFAULT '{}'::jsonb,
            archived boolean NOT NULL DEFAULT false,
            version_group_id character varying,
            storage jsonb,
            core_version character varying,
            updated timestamp with time zone NOT NULL DEFAULT now(),
            settings jsonb NOT NULL DEFAULT '{}'::jsonb,
            serialized_flow jsonb
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_flow_version ON flow(version int4_ops);
        CREATE INDEX ix_flow_name ON flow USING GIN (name gin_trgm_ops);
        CREATE INDEX ix_flow_version_group_id ON flow(version_group_id text_ops);
 
        """
    )

    op.execute(
        """

        -- Table Definition ----------------------------------------------

        CREATE TABLE flow_run (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created timestamp with time zone NOT NULL DEFAULT now(),
            flow_id uuid NOT NULL REFERENCES flow(id) ON DELETE CASCADE,
            parameters jsonb DEFAULT '{}'::jsonb,
            scheduled_start_time timestamp with time zone NOT NULL DEFAULT clock_timestamp(),
            auto_scheduled boolean NOT NULL DEFAULT false,
            heartbeat timestamp with time zone,
            start_time timestamp with time zone,
            end_time timestamp with time zone,
            duration interval,
            version integer NOT NULL DEFAULT 0,
            state character varying,
            state_timestamp timestamp with time zone,
            state_message character varying,
            state_result jsonb,
            state_start_time timestamp with time zone,
            serialized_state jsonb,
            name character varying,
            context jsonb,
            times_resurrected integer DEFAULT 0,
            updated timestamp with time zone NOT NULL DEFAULT now()
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_flow_run_flow_id ON flow_run(flow_id uuid_ops);
        CREATE INDEX ix_flow_run_heartbeat ON flow_run(heartbeat timestamptz_ops);
        CREATE INDEX ix_flow_run_state ON flow_run(state text_ops);
        CREATE INDEX ix_flow_run_start_time ON flow_run(start_time timestamptz_ops);
        CREATE INDEX ix_flow_run_name ON flow_run USING GIN (name gin_trgm_ops);
        CREATE INDEX ix_flow_run_flow_id_scheduled_start_time_for_hasura ON flow_run(flow_id uuid_ops,scheduled_start_time timestamptz_ops DESC);

        """
    )

    op.execute(
        """

        -- Table Definition ----------------------------------------------

        CREATE TABLE flow_run_state (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            flow_run_id uuid NOT NULL REFERENCES flow_run(id) ON DELETE CASCADE,
            timestamp timestamp with time zone NOT NULL DEFAULT clock_timestamp(),
            state character varying NOT NULL,
            message character varying,
            result jsonb,
            start_time timestamp with time zone,
            serialized_state jsonb NOT NULL,
            created timestamp with time zone NOT NULL DEFAULT now(),
            updated timestamp with time zone NOT NULL DEFAULT now(),
            version integer DEFAULT 0
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_flow_run_state_state ON flow_run_state(state text_ops);
        CREATE INDEX ix_flow_run_state_flow_run_id ON flow_run_state(flow_run_id uuid_ops);
        CREATE INDEX ix_flow_run_state_timestamp ON flow_run_state(timestamp timestamptz_ops);

        """
    )

    op.execute(
        """

        -- Table Definition ----------------------------------------------

        CREATE TABLE task (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created timestamp with time zone NOT NULL DEFAULT now(),
            flow_id uuid NOT NULL REFERENCES flow(id) ON DELETE CASCADE,
            name character varying,
            slug character varying,
            description character varying,
            type character varying,
            max_retries integer,
            retry_delay interval,
            trigger character varying,
            mapped boolean NOT NULL DEFAULT false,
            auto_generated boolean NOT NULL DEFAULT false,
            cache_key character varying,
            is_root_task boolean NOT NULL DEFAULT false,
            is_terminal_task boolean NOT NULL DEFAULT false,
            is_reference_task boolean NOT NULL DEFAULT false,
            tags jsonb NOT NULL DEFAULT '[]'::jsonb,
            updated timestamp with time zone NOT NULL DEFAULT now(),
            CONSTRAINT task_flow_id_slug_key UNIQUE (flow_id, slug)
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_task_flow_id ON task(flow_id uuid_ops);
        CREATE INDEX ix_task_name ON task USING GIN (name gin_trgm_ops);
        CREATE INDEX ix_task_tags ON task USING GIN (tags jsonb_ops);

        """
    )

    op.execute(
        """
        -- Table Definition ----------------------------------------------

        CREATE TABLE task_run (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created timestamp with time zone NOT NULL DEFAULT now(),
            flow_run_id uuid NOT NULL REFERENCES flow_run(id) ON DELETE CASCADE,
            task_id uuid NOT NULL REFERENCES task(id) ON DELETE CASCADE,
            map_index integer NOT NULL DEFAULT '-1'::integer,
            version integer NOT NULL DEFAULT 0,
            heartbeat timestamp with time zone,
            start_time timestamp with time zone,
            end_time timestamp with time zone,
            duration interval,
            run_count integer NOT NULL DEFAULT 0,
            state character varying,
            state_timestamp timestamp with time zone,
            state_message character varying,
            state_result jsonb,
            state_start_time timestamp with time zone,
            serialized_state jsonb,
            cache_key character varying,
            updated timestamp with time zone NOT NULL DEFAULT now(),
            CONSTRAINT task_run_unique_identifier_key UNIQUE (flow_run_id, task_id, map_index)
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_task_run_heartbeat ON task_run(heartbeat timestamptz_ops);
        CREATE INDEX ix_task_run_state ON task_run(state text_ops);
        CREATE INDEX ix_task_run_flow_run_id ON task_run(flow_run_id uuid_ops);
        CREATE INDEX ix_task_run_task_id ON task_run(task_id uuid_ops);
        CREATE INDEX ix_task_run_cache_key ON task_run(cache_key text_ops);
        
        """
    )

    op.execute(
        """
        -- Table Definition ----------------------------------------------

        CREATE TABLE task_run_state (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            task_run_id uuid NOT NULL REFERENCES task_run(id) ON DELETE CASCADE,
            timestamp timestamp with time zone NOT NULL DEFAULT clock_timestamp(),
            state character varying NOT NULL,
            message character varying,
            result jsonb,
            start_time timestamp with time zone,
            serialized_state jsonb NOT NULL,
            created timestamp with time zone NOT NULL DEFAULT now(),
            updated timestamp with time zone NOT NULL DEFAULT now(),
            version integer DEFAULT 0
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_task_run_state_timestamp ON task_run_state(timestamp timestamptz_ops);
        CREATE INDEX ix_task_run_state_task_run_id ON task_run_state(task_run_id uuid_ops);
        CREATE INDEX ix_task_run_state_state ON task_run_state(state text_ops);

        """
    )

    op.execute(
        """

        -- Table Definition ----------------------------------------------

        CREATE TABLE schedule (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created timestamp with time zone NOT NULL DEFAULT now(),
            flow_id uuid NOT NULL REFERENCES flow(id) ON DELETE CASCADE,
            schedule jsonb NOT NULL,
            active boolean NOT NULL DEFAULT false,
            schedule_start timestamp with time zone,
            schedule_end timestamp with time zone,
            last_checked timestamp with time zone,
            last_scheduled_run_time timestamp with time zone,
            updated timestamp with time zone NOT NULL DEFAULT now()
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_schedule_flow_id ON schedule(flow_id uuid_ops);
        CREATE INDEX ix_schedule_schedule_end ON schedule(schedule_end timestamptz_ops);
        CREATE INDEX ix_schedule_last_scheduled_run_time ON schedule(last_scheduled_run_time timestamptz_ops);
        CREATE INDEX ix_schedule_last_checked ON schedule(last_checked timestamptz_ops);
        CREATE INDEX ix_schedule_schedule_start ON schedule(schedule_start timestamptz_ops);
        CREATE INDEX ix_schedule_active ON schedule(active bool_ops);

        """
    )
    op.execute(
        """

        -- Table Definition ----------------------------------------------

        CREATE TABLE edge (
            id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
            created timestamp with time zone NOT NULL DEFAULT now(),
            flow_id uuid NOT NULL REFERENCES flow(id) ON DELETE CASCADE,
            upstream_task_id uuid NOT NULL REFERENCES task(id) ON DELETE CASCADE,
            downstream_task_id uuid NOT NULL REFERENCES task(id) ON DELETE CASCADE,
            key character varying,
            mapped boolean NOT NULL DEFAULT false,
            updated timestamp with time zone NOT NULL DEFAULT now()
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_edge_upstream_task_id ON edge(upstream_task_id uuid_ops);
        CREATE INDEX ix_edge_downstream_task_id ON edge(downstream_task_id uuid_ops);
        CREATE INDEX ix_edge_flow_id ON edge(flow_id uuid_ops);
        
        """
    )
    op.execute(
        """
        
        -- Table Definition ----------------------------------------------

        CREATE TABLE log (
            flow_run_id uuid REFERENCES flow_run(id) ON DELETE CASCADE,
            task_run_id uuid REFERENCES task_run(id) ON DELETE CASCADE,
            timestamp timestamp with time zone NOT NULL DEFAULT '2020-03-18 13:42:43.118776+00'::timestamp with time zone,
            name character varying,
            level character varying,
            message character varying,
            info jsonb,
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            created timestamp with time zone NOT NULL DEFAULT now(),
            updated timestamp with time zone NOT NULL DEFAULT now()
        );

        -- Indices -------------------------------------------------------

        CREATE INDEX ix_log_flow_run_id ON log(flow_run_id uuid_ops);
        CREATE INDEX ix_log_task_run_id ON log(task_run_id uuid_ops);
        CREATE INDEX ix_log_timestamp ON log(timestamp timestamptz_ops DESC);

        """
    )

    # --------------------------------------------------------------------------
    # Circular relationships
    # --------------------------------------------------------------------------
    op.add_column(
        "flow_run",
        sa.Column(
            "state_id", UUID, sa.ForeignKey("flow_run_state.id", ondelete="SET NULL")
        ),
    )

    op.add_column(
        "task_run",
        sa.Column(
            "state_id", UUID, sa.ForeignKey("task_run_state.id", ondelete="SET NULL")
        ),
    )

    op.create_index("ix_flow_run__state_id", "flow_run", ["state_id"])

    op.create_index("ix_task_run__state_id", "task_run", ["state_id"])

    op.execute("CREATE SCHEMA utility;")
    op.create_table(
        "traversal",
        sa.Column("task_id", UUID),
        sa.Column("depth", sa.Integer),
        schema="utility",
    )

    op.execute(
        """
        CREATE FUNCTION utility.downstream_tasks(start_task_ids UUID[], depth_limit integer default 50)
        RETURNS SETOF utility.traversal AS

        $$
        with recursive traverse(task_id, depth) AS (
            SELECT
                -- a task id
                edge.upstream_task_id,

                -- the depth
                0

            FROM edge

            -- the starting point
            WHERE edge.upstream_task_id = ANY(start_task_ids)

            UNION

            SELECT

                -- a new task
                edge.downstream_task_id,

                -- increment the depth
                traverse.depth + 1

            FROM traverse
            INNER JOIN edge
            ON
                edge.upstream_task_id = traverse.task_id
            WHERE

                -- limit traversal to the lesser of 50 tasks or the depth_limit
                traverse.depth < 50
                AND traverse.depth < depth_limit
            )
        SELECT
            task_id,
            MAX(traverse.depth) as depth
        FROM traverse

        -- group by task_id to remove duplicate observations
        GROUP BY task_id

        -- sort by the last time a task was visited
        ORDER BY MAX(traverse.depth)

        $$ LANGUAGE sql STABLE;
    """
    )
    op.execute(
        """
        CREATE FUNCTION utility.upstream_tasks(start_task_ids UUID[], depth_limit integer default 50)
        RETURNS SETOF utility.traversal AS

        $$
        with recursive traverse(task_id, depth) AS (
            SELECT

                -- a task id
                edge.downstream_task_id,

                -- the depth
                0

            FROM edge

            -- the starting point
            WHERE edge.downstream_task_id = ANY(start_task_ids)

            UNION

            SELECT

                -- a new task
                edge.upstream_task_id,

                -- increment the depth
                traverse.depth + 1

            FROM traverse
            INNER JOIN edge
            ON
                edge.downstream_task_id = traverse.task_id
            WHERE

                -- limit traversal to the lesser of 50 tasks or the depth_limit
                traverse.depth < 50
                AND traverse.depth < depth_limit
            )
        SELECT
            task_id,
            MAX(traverse.depth) as depth
        FROM traverse

        -- group by task_id to remove duplicate observations
        GROUP BY task_id

        -- sort by the last time a task was visited
        ORDER BY MAX(traverse.depth)

        $$ LANGUAGE sql STABLE;
    """
    )


def downgrade():
    op.execute("DROP SCHEMA utility CASCADE;")
    op.execute(
        """
        DROP TABLE edge CASCADE;
        DROP TABLE flow CASCADE;
        DROP TABLE flow_run CASCADE;
        DROP TABLE flow_run_state CASCADE;
        DROP TABLE log CASCADE;
        DROP TABLE schedule CASCADE;
        DROP TABLE task CASCADE;
        DROP TABLE task_run CASCADE;
        DROP TABLE task_run_state CASCADE;
        """
    )
