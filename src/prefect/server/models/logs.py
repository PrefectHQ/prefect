"""
Functions for interacting with log ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Generator, Optional, Sequence, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database import PrefectDBInterface, db_injector, orm_models
from prefect.server.schemas.actions import LogCreate
from prefect.server.schemas.core import Log
from prefect.utilities.collections import batched_iterable

# We have a limit of 32,767 parameters at a time for a single query...
MAXIMUM_QUERY_PARAMETERS = 32_767

# ...and logs have a certain number of fields...
NUMBER_OF_LOG_FIELDS = len(Log.model_fields)

# ...so we can only INSERT batches of a certain size at a time
LOG_BATCH_SIZE = MAXIMUM_QUERY_PARAMETERS // NUMBER_OF_LOG_FIELDS

def split_logs_into_batches(
    logs: Sequence[Log],
) -> Generator[Tuple[Log, ...], None, None]:
    for batch in batched_iterable(logs, LOG_BATCH_SIZE):
        yield batch


def _sanitize_log_strings(log: Log) -> Log:
    """Strip null bytes from log string fields.

    PostgreSQL rejects strings containing null bytes (0x00) with
    `CharacterNotInRepertoireError`.  Rather than letting the INSERT
    fail, we replace them here so the rest of the log record is preserved.
    """
    sanitized_message = log.message.replace("\x00", "")
    sanitized_name = log.name.replace("\x00", "")
    if sanitized_message != log.message or sanitized_name != log.name:
        return log.model_copy(
            update={"message": sanitized_message, "name": sanitized_name}
        )
    return log


@db_injector
async def create_logs(
    db: PrefectDBInterface, session: AsyncSession, logs: Sequence[Log]
) -> None:
    """Persist logs in the Prefect database.

    Args:
        session: A database session.
        logs: The logs to persist.

    Returns:
        None
    """
    logs = [_sanitize_log_strings(log) for log in logs]
    await session.execute(
        db.queries.insert(db.Log).values(
            [log.model_dump(exclude={"created", "updated"}) for log in logs]
        )
    )


@db_injector
async def read_logs(
    db: PrefectDBInterface,
    session: AsyncSession,
    log_filter: Optional[schemas.filters.LogFilter],
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    sort: schemas.sorting.LogSort = schemas.sorting.LogSort.TIMESTAMP_ASC,
) -> Sequence[orm_models.Log]:
    """
    Read logs.

    Args:
        session: a database session
        db: the database interface
        log_filter: only select logs that match these filters
        offset: Query offset
        limit: Query limit
        sort: Query sort

    Returns:
        List[orm_models.Log]: the matching logs
    """
    query = select(db.Log).order_by(*sort.as_sql_sort()).offset(offset).limit(limit)

    if log_filter:
        query = query.where(log_filter.as_sql_filter())

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def delete_logs(
    db: PrefectDBInterface,
    session: AsyncSession,
    log_filter: schemas.filters.LogFilter,
) -> int:
    query = delete(db.Log).where(log_filter.as_sql_filter())
    result = await session.execute(query)
    return result.rowcount
