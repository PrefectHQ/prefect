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
