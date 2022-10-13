"""
Functions for interacting with log ORM objects.
Intended for internal use by the Orion API.
"""
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.utilities.collections import batched_iterable

# We have a limit of 32,767 parameters at a time for a single query...
MAXIMUM_QUERY_PARAMETERS = 32_767

# ...and logs have a certain number of fields...
NUMBER_OF_LOG_FIELDS = len(schemas.core.Log.schema()["properties"])

# ...so we can only INSERT batches of a certain size at a time
LOG_BATCH_SIZE = MAXIMUM_QUERY_PARAMETERS // NUMBER_OF_LOG_FIELDS


def split_logs_into_batches(logs):
    for batch in batched_iterable(logs, LOG_BATCH_SIZE):
        yield batch


@inject_db
async def create_logs(
    session: AsyncSession, db: OrionDBInterface, logs: List[schemas.core.Log]
):
    """
    Creates new logs

    Args:
        session: a database session
        logs: a list of log schemas

    Returns:
        None
    """
    log_insert = await db.insert(db.Log)
    await session.execute(log_insert.values([log.dict() for log in logs]))


@inject_db
async def read_logs(
    session: AsyncSession,
    db: OrionDBInterface,
    log_filter: schemas.filters.LogFilter,
    offset: int = None,
    limit: int = None,
    sort: schemas.sorting.LogSort = schemas.sorting.LogSort.TIMESTAMP_ASC,
):
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
        List[db.Log]: the matching logs
    """
    query = select(db.Log).order_by(sort.as_sql_sort(db)).offset(offset).limit(limit)

    if log_filter:
        query = query.where(log_filter.as_sql_filter(db))

    result = await session.execute(query)
    return result.scalars().unique().all()
