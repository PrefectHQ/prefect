"""
Functions for interacting with log ORM objects.
Intended for internal use by the Orion API.
"""
from typing import List

import sqlalchemy as sa
from sqlalchemy import select

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


@inject_db
async def create_logs(
    session: sa.orm.Session, db: OrionDBInterface, logs: List[schemas.core.Log]
):
    """
    Creates new logs.

    Args:
        session: a database session
        logs: a list of log schemas

    Returns:
        None
    """
    insert_stmt = (await db.insert(db.Log)).values([log.dict() for log in logs])
    await session.execute(insert_stmt)


@inject_db
async def read_logs(
    session: sa.orm.Session,
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
