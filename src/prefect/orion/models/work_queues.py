"""
Functions for interacting with work queue ORM objects.
Intended for internal use by the Orion API.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


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
        bool: whether or not the WorkQueue was deleted
    """
    if not isinstance(work_queue, schemas.actions.WorkQueueUpdate):
        raise ValueError(
            f"Expected parameter flow to have type schemas.actions.WorkQueueUpdate, got {type(work_queue)!r} instead"
        )

    update_stmt = (
        sa.update(db.WorkQueue).where(db.WorkQueue.id == work_queue_id)
        # exclude_unset=True allows us to only update values provided by
        # the user, ignoring any defaults on the model
        .values(**work_queue.dict(shallow=True, exclude_unset=True))
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
