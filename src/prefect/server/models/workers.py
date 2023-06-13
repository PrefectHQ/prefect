"""
Functions for interacting with worker ORM objects.
Intended for internal use by the Prefect REST API.
"""
import datetime
from typing import Dict, List, Optional
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.database.orm_models import ORMWorker, ORMWorkPool, ORMWorkQueue

DEFAULT_AGENT_WORK_POOL_NAME = "default-agent-pool"

# -----------------------------------------------------
# --
# --
# -- Work Pools
# --
# --
# -----------------------------------------------------


@inject_db
async def create_work_pool(
    session: AsyncSession,
    work_pool: schemas.core.WorkPool,
    db: PrefectDBInterface,
) -> ORMWorkPool:
    """
    Creates a work pool.

    If a WorkPool with the same name exists, an error will be thrown.

    Args:
        session (AsyncSession): a database session
        work_pool (schemas.core.WorkPool): a WorkPool model

    Returns:
        db.WorkPool: the newly-created WorkPool

    """

    pool = db.WorkPool(**work_pool.dict())
    session.add(pool)
    await session.flush()

    default_queue = await create_work_queue(
        session=session,
        work_pool_id=pool.id,
        work_queue=schemas.actions.WorkQueueCreate(
            name="default", description="The work pool's default queue."
        ),
    )

    pool.default_queue_id = default_queue.id
    await session.flush()

    return pool


@inject_db
async def read_work_pool(
    session: AsyncSession, work_pool_id: UUID, db: PrefectDBInterface
) -> ORMWorkPool:
    """
    Reads a WorkPool by id.

    Args:
        session (AsyncSession): A database session
        work_pool_id (UUID): a WorkPool id

    Returns:
        db.WorkPool: the WorkPool
    """
    query = sa.select(db.WorkPool).where(db.WorkPool.id == work_pool_id).limit(1)
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_work_pool_by_name(
    session: AsyncSession, work_pool_name: str, db: PrefectDBInterface
) -> ORMWorkPool:
    """
    Reads a WorkPool by name.

    Args:
        session (AsyncSession): A database session
        work_pool_name (str): a WorkPool name

    Returns:
        db.WorkPool: the WorkPool
    """
    query = sa.select(db.WorkPool).where(db.WorkPool.name == work_pool_name).limit(1)
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_work_pools(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_filter: schemas.filters.WorkPoolFilter = None,
    offset: int = None,
    limit: int = None,
) -> List[ORMWorkPool]:
    """
    Read worker configs.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
    Returns:
        List[db.WorkPool]: worker configs
    """

    query = select(db.WorkPool).order_by(db.WorkPool.name)

    if work_pool_filter is not None:
        query = query.where(work_pool_filter.as_sql_filter(db))
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_work_pool(
    session: AsyncSession,
    work_pool_id: UUID,
    work_pool: schemas.actions.WorkPoolUpdate,
    db: PrefectDBInterface,
) -> bool:
    """
    Update a WorkPool by id.

    Args:
        session (AsyncSession): A database session
        work_pool_id (UUID): a WorkPool id
        worker: the work queue data

    Returns:
        bool: whether or not the worker was updated
    """
    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = work_pool.dict(shallow=True, exclude_unset=True)

    update_stmt = (
        sa.update(db.WorkPool)
        .where(db.WorkPool.id == work_pool_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def delete_work_pool(
    session: AsyncSession, work_pool_id: UUID, db: PrefectDBInterface
) -> bool:
    """
    Delete a WorkPool by id.

    Args:
        session (AsyncSession): A database session
        work_pool_id (UUID): a work pool id

    Returns:
        bool: whether or not the WorkPool was deleted
    """

    result = await session.execute(
        delete(db.WorkPool).where(db.WorkPool.id == work_pool_id)
    )
    return result.rowcount > 0


@inject_db
async def get_scheduled_flow_runs(
    session: AsyncSession,
    work_pool_ids: List[UUID] = None,
    work_queue_ids: List[UUID] = None,
    scheduled_before: datetime.datetime = None,
    scheduled_after: datetime.datetime = None,
    limit: int = None,
    respect_queue_priorities: bool = None,
    db: PrefectDBInterface = None,
) -> List[schemas.responses.WorkerFlowRunResponse]:
    """
    Get runs from queues in a specific work pool.

    Args:
        session (AsyncSession): a database session
        work_pool_ids (List[UUID]): a list of work pool ids
        work_queue_ids (List[UUID]): a list of work pool queue ids
        scheduled_before (datetime.datetime): a datetime to filter runs scheduled before
        scheduled_after (datetime.datetime): a datetime to filter runs scheduled after
        respect_queue_priorities (bool): whether or not to respect queue priorities
        limit (int): the maximum number of runs to return
        db: a database interface

    Returns:
        List[WorkerFlowRunResponse]: the runs, as well as related work pool details

    """

    if respect_queue_priorities is None:
        respect_queue_priorities = True

    return await db.queries.get_scheduled_flow_runs_from_work_pool(
        session=session,
        db=db,
        work_pool_ids=work_pool_ids,
        work_queue_ids=work_queue_ids,
        scheduled_before=scheduled_before,
        scheduled_after=scheduled_after,
        respect_queue_priorities=respect_queue_priorities,
        limit=limit,
    )


# -----------------------------------------------------
# --
# --
# -- Work Pool Queues
# --
# --
# -----------------------------------------------------


@inject_db
async def create_work_queue(
    session: AsyncSession,
    work_pool_id: UUID,
    work_queue: schemas.actions.WorkQueueCreate,
    db: PrefectDBInterface,
) -> ORMWorkQueue:
    """
    Creates a work pool queue.

    Args:
        session (AsyncSession): a database session
        work_pool_id (UUID): a work pool id
        work_queue (schemas.actions.WorkQueueCreate): a WorkQueue action model

    Returns:
        db.WorkQueue: the newly-created WorkQueue

    """
    data = work_queue.dict(exclude={"work_pool_id"})
    if work_queue.priority is None:
        # Set the priority to be the first priority value that isn't already taken
        priorities_query = sa.select(db.WorkQueue.priority).where(
            db.WorkQueue.work_pool_id == work_pool_id
        )
        priorities = (await session.execute(priorities_query)).scalars().all()

        priority = None
        for i, p in enumerate(sorted(priorities)):
            # if a rank was skipped (e.g. the set priority is different than the
            # enumerated priority) then we can "take" that spot for this work
            # queue
            if i + 1 != p:
                priority = i + 1
                break

        # otherwise take the maximum priority plus one
        if priority is None:
            priority = max(priorities, default=0) + 1

        data["priority"] = priority

    model = db.WorkQueue(**data, work_pool_id=work_pool_id)

    session.add(model)
    await session.flush()
    await session.refresh(model)

    if work_queue.priority:
        await bulk_update_work_queue_priorities(
            session=session,
            work_pool_id=work_pool_id,
            new_priorities={model.id: work_queue.priority},
            db=db,
        )
    return model


@inject_db
async def bulk_update_work_queue_priorities(
    session: AsyncSession,
    work_pool_id: UUID,
    new_priorities: Dict[UUID, int],
    db: PrefectDBInterface,
):
    """
    This is a brute force update of all work pool queue priorities for a given work
    pool.

    It loads all queues fully into memory, sorts them, and flushes the update to
    the db. The algorithm ensures that priorities are unique integers > 0, and
    makes the minimum number of changes required to satisfy the provided
    `new_priorities`. For example, if no queues currently have the provided
    `new_priorities`, then they are assigned without affecting other queues. If
    they are held by other queues, then those queues' priorities are
    incremented as necessary.

    Updating queue priorities is not a common operation (happens on the same scale as
    queue modification, which is significantly less than reading from queues),
    so while this implementation is slow, it may suffice and make up for that
    with extreme simplicity.
    """

    if len(set(new_priorities.values())) != len(new_priorities):
        raise ValueError("Duplicate target priorities provided")

    # get all the work queues, sorted by priority
    work_queues_query = (
        sa.select(db.WorkQueue)
        .where(db.WorkQueue.work_pool_id == work_pool_id)
        .order_by(db.WorkQueue.priority.asc())
    )
    result = await session.execute(work_queues_query)
    all_work_queues = result.scalars().all()

    # split the queues into those that need to be updated and those that don't
    work_queues = [wq for wq in all_work_queues if wq.id not in new_priorities]
    updated_queues = [wq for wq in all_work_queues if wq.id in new_priorities]

    # update queue priorities and insert them into the appropriate place in the
    # full list of queues
    for queue in sorted(updated_queues, key=lambda wq: new_priorities[wq.id]):
        queue.priority = new_priorities[queue.id]
        for i, wq in enumerate(work_queues):
            if wq.priority >= new_priorities[queue.id]:
                work_queues.insert(i, queue)
                break

    # walk through the queues and update their priorities such that the
    # priorities are sequential. Do this by tracking that last priority seen and
    # ensuring that each successive queue's priority is higher than it. This
    # will maintain queue order and ensure increasing priorities with minimal
    # changes.
    last_priority = 0
    for queue in work_queues:
        if queue.priority <= last_priority:
            last_priority += 1
            queue.priority = last_priority
        else:
            last_priority = queue.priority

    await session.flush()


@inject_db
async def read_work_queues(
    session: AsyncSession,
    work_pool_id: UUID,
    db: PrefectDBInterface,
    work_queue_filter: Optional[schemas.filters.WorkQueueFilter] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[ORMWorkQueue]:
    """
    Read all work pool queues for a work pool. Results are ordered by ascending priority.

    Args:
        session (AsyncSession): a database session
        work_pool_id (UUID): a work pool id
        work_queue_filter: Filter criteria for work pool queues
        offset: Query offset
        limit: Query limit


    Returns:
        List[db.WorkQueue]: the WorkQueues

    """
    query = (
        sa.select(db.WorkQueue)
        .where(db.WorkQueue.work_pool_id == work_pool_id)
        .order_by(db.WorkQueue.priority.asc())
    )

    if work_queue_filter is not None:
        query = query.where(work_queue_filter.as_sql_filter(db))
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def read_work_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    db: PrefectDBInterface,
) -> ORMWorkQueue:
    """
    Read a specific work pool queue.

    Args:
        session (AsyncSession): a database session
        work_queue_id (UUID): a work pool queue id

    Returns:
        db.WorkQueue: the WorkQueue

    """
    return await session.get(db.WorkQueue, work_queue_id)


@inject_db
async def read_work_queue_by_name(
    session: AsyncSession,
    work_pool_name: str,
    work_queue_name: str,
    db: PrefectDBInterface,
) -> ORMWorkQueue:
    """
    Reads a WorkQueue by name.

    Args:
        session (AsyncSession): A database session
        work_pool_name (str): a WorkPool name
        work_queue_name (str): a WorkQueue name

    Returns:
        db.WorkQueue: the WorkQueue
    """
    query = (
        sa.select(db.WorkQueue)
        .join(db.WorkPool, db.WorkPool.id == db.WorkQueue.work_pool_id)
        .where(
            db.WorkPool.name == work_pool_name,
            db.WorkQueue.name == work_queue_name,
        )
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def update_work_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    work_queue: schemas.actions.WorkQueueUpdate,
    db: PrefectDBInterface,
) -> bool:
    """
    Update a work pool queue.

    Args:
        session (AsyncSession): a database session
        work_queue_id (UUID): a work pool queue ID
        work_queue (schemas.actions.WorkQueueUpdate): a WorkQueue model

    Returns:
        bool: whether or not the WorkQueue was updated

    """
    update_values = work_queue.dict(shallow=True, exclude_unset=True)
    update_stmt = (
        sa.update(db.WorkQueue)
        .where(db.WorkQueue.id == work_queue_id)
        .values(update_values)
    )
    result = await session.execute(update_stmt)

    if result.rowcount > 0 and "priority" in update_values:
        work_queue = await session.get(db.WorkQueue, work_queue_id)
        await bulk_update_work_queue_priorities(
            session,
            work_pool_id=work_queue.work_pool_id,
            new_priorities={work_queue_id: update_values["priority"]},
        )
    return result.rowcount > 0


@inject_db
async def delete_work_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    db: PrefectDBInterface,
) -> bool:
    """
    Delete a work pool queue.

    Args:
        session (AsyncSession): a database session
        work_queue_id (UUID): a work pool queue ID

    Returns:
        bool: whether or not the WorkQueue was deleted

    """
    work_queue = await session.get(db.WorkQueue, work_queue_id)
    if work_queue is None:
        return False

    await session.delete(work_queue)
    try:
        await session.flush()

    # if an error was raised, check if the user tried to delete a default queue
    except sa.exc.IntegrityError as exc:
        if "foreign key constraint" in str(exc).lower():
            raise ValueError("Can't delete a pool's default queue.")
        raise

    await bulk_update_work_queue_priorities(
        session,
        work_pool_id=work_queue.work_pool_id,
        new_priorities={},
    )
    return True


# -----------------------------------------------------
# --
# --
# -- Workers
# --
# --
# -----------------------------------------------------


@inject_db
async def read_workers(
    session: AsyncSession,
    work_pool_id: UUID,
    worker_filter: schemas.filters.WorkerFilter = None,
    limit: int = None,
    offset: int = None,
    db: PrefectDBInterface = None,
) -> List[ORMWorker]:
    query = (
        sa.select(db.Worker)
        .where(db.Worker.work_pool_id == work_pool_id)
        .order_by(db.Worker.last_heartbeat_time.desc())
        .limit(limit)
    )

    if worker_filter:
        query = query.where(worker_filter.as_sql_filter(db))

    if limit is not None:
        query = query.limit(limit)

    if offset is not None:
        query = query.offset(offset)

    result = await session.execute(query)
    return result.scalars().all()


@inject_db
async def worker_heartbeat(
    session: AsyncSession,
    work_pool_id: UUID,
    worker_name: str,
    db: PrefectDBInterface,
) -> bool:
    """
    Record a worker process heartbeat.

    Args:
        session (AsyncSession): a database session
        work_pool_id (UUID): a work pool ID
        worker_name (str): a worker name

    Returns:
        bool: whether or not the worker was updated

    """
    now = pendulum.now("UTC")
    insert_stmt = (
        (await db.insert(db.Worker))
        .values(
            work_pool_id=work_pool_id,
            name=worker_name,
            last_heartbeat_time=now,
        )
        .on_conflict_do_update(
            index_elements=[
                db.Worker.work_pool_id,
                db.Worker.name,
            ],
            set_=dict(last_heartbeat_time=now),
        )
    )

    result = await session.execute(insert_stmt)
    return result.rowcount > 0
