"""
Functions for interacting with log ORM objects.
Intended for internal use by the Prefect REST API.
"""

from typing import Generator, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas.actions import LogCreate
from prefect.utilities.collections import batched_iterable

# We have a limit of 32,767 parameters at a time for a single query...
MAXIMUM_QUERY_PARAMETERS = 32_767

# ...and logs have a certain number of fields...
NUMBER_OF_LOG_FIELDS = len(schemas.core.Log.model_fields)

# ...so we can only INSERT batches of a certain size at a time
LOG_BATCH_SIZE = MAXIMUM_QUERY_PARAMETERS // NUMBER_OF_LOG_FIELDS

logger = get_logger(__name__)


def split_logs_into_batches(
    logs: List[schemas.actions.LogCreate],
) -> Generator[Tuple[LogCreate, ...], None, None]:
    for batch in batched_iterable(logs, LOG_BATCH_SIZE):
        yield batch


@db_injector
async def create_logs(
    db: PrefectDBInterface, session: AsyncSession, logs: List[schemas.core.Log]
) -> None:
    """
    Creates new logs

    Args:
        session: a database session
        logs: a list of log schemas

    Returns:
        None
    """
    try:
        await session.execute(
            db.insert(orm_models.Log).values([log.model_dump() for log in logs])
        )
    except RuntimeError as exc:
        if "can't create new thread at interpreter shutdown" in str(exc):
            # Background logs sometimes fail to write when the interpreter is shutting down.
            # This is a known issue in Python 3.12.2 that can be ignored and is fixed in Python 3.12.3.
            # see e.g. https://github.com/python/cpython/issues/113964
            logger.debug("Received event during interpreter shutdown, ignoring")
        else:
            raise


async def read_logs(
    session: AsyncSession,
    log_filter: schemas.filters.LogFilter,
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
    query = (
        select(orm_models.Log).order_by(sort.as_sql_sort()).offset(offset).limit(limit)
    )

    if log_filter:
        query = query.where(log_filter.as_sql_filter())

    result = await session.execute(query)
    return result.scalars().unique().all()
