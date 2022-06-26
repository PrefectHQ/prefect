"""
Functions for interacting with work queue ORM objects.
Intended for internal use by the Orion API.
"""

import datetime
from uuid import UUID

import sqlalchemy as sa
from pydantic import parse_obj_as
from sqlalchemy import delete, select

import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.exceptions import ObjectNotFoundError


@inject_db
async def create_work_queue(
    session: sa.orm.Session,
    work_queue: schemas.core.WorkQueue,
    db: OrionDBInterface,
):
    """
    Inserts a WorkQueue.

    If a WorkQueue with the same name exists, an error will be thrown.

    Args:
        session (sa.orm.Session): a database session
        work_queue (schemas.core.WorkQueue): a WorkQueue model

    Returns:
        db.WorkQueue: the newly-created or updated WorkQueue

    """

    model = db.WorkQueue(**work_queue.dict())
    session.add(model)
    await session.flush()

    return model


@inject_db
async def read_work_queue(
    session: sa.orm.Session, work_queue_id: UUID, db: OrionDBInterface
):
    """
    Reads a WorkQueue by id.

    Args:
        session (sa.orm.Session): A database session
        work_queue_id (str): a WorkQueue id

    Returns:
        db.WorkQueue: the WorkQueue
    """

    return await session.get(db.WorkQueue, work_queue_id)


@inject_db
async def read_work_queue_by_name(
    session: sa.orm.Session, name: str, db: OrionDBInterface
):
    """
    Reads a WorkQueue by id.

    Args:
        session (sa.orm.Session): A database session
        work_queue_id (str): a WorkQueue id

    Returns:
        db.WorkQueue: the WorkQueue
    """

    query = select(db.WorkQueue).filter_by(name=name)
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_work_queues(
    db: OrionDBInterface,
    session: sa.orm.Session,
    offset: int = None,
    limit: int = None,
):
    """
    Read WorkQueues.

    Args:
        session (sa.orm.Session): A database session
        offset (int): Query offset
        limit(int): Query limit

    Returns:
        List[db.WorkQueue]: WorkQueues
    """

    query = select(db.WorkQueue).order_by(db.WorkQueue.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_work_queue(
    session: sa.orm.Session,
    work_queue_id: UUID,
    work_queue: schemas.actions.WorkQueueUpdate,
    db: OrionDBInterface,
) -> bool:
    """
    Update a WorkQueue by id.

    Args:
        session (sa.orm.Session): A database session
        work_queue: the work queue data
        work_queue_id (str): a WorkQueue id

    Returns:
        bool: whether or not the WorkQueue was updated
    """
    if not isinstance(work_queue, schemas.actions.WorkQueueUpdate):
        raise ValueError(
            f"Expected parameter flow to have type schemas.actions.WorkQueueUpdate, got {type(work_queue)!r} instead"
        )

    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = work_queue.dict(shallow=True, exclude_unset=True)

    update_stmt = (
        sa.update(db.WorkQueue)
        .where(db.WorkQueue.id == work_queue_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def delete_work_queue(
    session: sa.orm.Session, work_queue_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a WorkQueue by id.

    Args:
        session (sa.orm.Session): A database session
        work_queue_id (str): a WorkQueue id

    Returns:
        bool: whether or not the WorkQueue was deleted
    """

    result = await session.execute(
        delete(db.WorkQueue).where(db.WorkQueue.id == work_queue_id)
    )
    return result.rowcount > 0


async def get_runs_in_work_queue(
    session: sa.orm.Session,
    work_queue_id: UUID,
    scheduled_before: datetime.datetime,
    limit: int = None,
):
    """
    Get runs from a work queue.

    Args:
        session: A database session.
        work_queue_id: The work queue id.
        scheduled_before: Only return runs scheduled to start before this time.
        limit: An optional limit for the number of runs to return from the queue.
            This limit applies to the request only. It does not affect the
            work queue's concurrency limit. If `limit` exceeds the work queue's
            concurrency limit, it will be ignored.

    """
    work_queue = await read_work_queue(session=session, work_queue_id=work_queue_id)
    if not work_queue:
        raise ObjectNotFoundError(f"Work queue with id {work_queue_id} not found.")

    if work_queue.is_paused:
        return []

    # ensure the filter object is fully hydrated
    # SQLAlchemy caching logic can result in a dict type instead
    # of the full pydantic model
    work_queue_filter = parse_obj_as(schemas.core.QueueFilter, work_queue.filter)

    # if the work queue has a concurrency limit, check how many runs are currently
    # executing and compare that count to the concurrency limit
    if work_queue.concurrency_limit:
        # Note this does not guarantee race conditions wont be hit
        concurrent_count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_run_filter=work_queue_filter.get_executing_flow_run_filter(),
        )

        # compute the available concurrency slots
        open_concurrency_slots = max(0, work_queue.concurrency_limit - concurrent_count)

        # if a limit override was given, ensure we return no more
        # than that limit
        if limit is not None:
            open_concurrency_slots = min(open_concurrency_slots, limit)
    else:
        # otherwise, the amount of flow runs to return is only controlled
        # by the limit given
        open_concurrency_slots = limit

    return await models.flow_runs.read_flow_runs(
        session=session,
        flow_run_filter=work_queue_filter.get_scheduled_flow_run_filter(
            scheduled_before=scheduled_before
        ),
        limit=open_concurrency_slots,
        sort=schemas.sorting.FlowRunSort.NEXT_SCHEDULED_START_TIME_ASC,
    )
