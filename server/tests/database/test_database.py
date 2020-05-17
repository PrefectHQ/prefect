# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import sqlalchemy as sa
from prefect_server import config


def test_ui_dashboard_index_exists(sqlalchemy_engine):
    """
    Even though it looks redundant, this index is necessary because of how Hasura generates SQL for the "flows" table on the UI dashboard. Without it that
    table takes forever to load.

    This could be fixed either by optimizing that query, or better SQL generation in Hasura, but until then it should not be deleted without cause.

    This test makes sure the index exists.
    """
    engine = sa.create_engine(config.database.connection_url)
    query = """
        SELECT
            count(*) as count
        FROM
            pg_indexes
        WHERE
            schemaname = 'public'
            AND tablename = 'flow_run'
            AND indexname = 'ix_flow_run_flow_id_scheduled_start_time_for_hasura'
        """
    result = engine.execute(query).fetchall()
    assert result[0]["count"] == 1
