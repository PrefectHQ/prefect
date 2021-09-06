import sqlalchemy as sa

from prefect.orion.utilities.database import (
    Base,
)


# in order to index or created generated columns from timestamps stored in JSON,
# we need a custom IMMUTABLE function for casting to timestamp
# (because timestamp is not actually immutable)
sa.event.listen(
    Base.metadata,
    "before_create",
    sa.DDL(
        """
        CREATE OR REPLACE FUNCTION text_to_timestamp_immutable(ts text)
        RETURNS timestamp with time zone
        AS
        $BODY$
            select to_timestamp($1, 'YYYY-MM-DD"T"HH24:MI:SS"Z"');
        $BODY$
        LANGUAGE sql
        IMMUTABLE;
        """
    ).execute_if(dialect="postgresql"),
)

sa.event.listen(
    Base.metadata,
    "before_drop",
    sa.DDL(
        """
        DROP FUNCTION IF EXISTS text_to_timestamp_immutable;
        """
    ).execute_if(dialect="postgresql"),
)


# # postgres indexes on json values
# sa.event.listen(
#     Base.metadata,
#     "after_create",
#     sa.DDL(
#         """
#         CREATE INDEX ix_flow_run_current_state_type_json
#         on flow_run ((run_details ->> 'current_state_type'));
#         """
#     ).execute_if(dialect="postgresql"),
# )

# # postgres indexes on json values
# sa.event.listen(
#     Base.metadata,
#     "after_create",
#     sa.DDL(
#         """
#         CREATE INDEX ix_flow_run_expected_start_time_json
#         on flow_run (text_to_timestamp(run_details ->> 'expected_start_time'));
#         """
#     ).execute_if(dialect="postgresql"),
# )
