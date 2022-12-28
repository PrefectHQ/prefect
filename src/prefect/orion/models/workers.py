"""
Functions for interacting with worker ORM objects.
Intended for internal use by the Orion API.
"""
import datetime
from typing import Dict, List
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.database.orm_models import (
    ORMWorker,
    ORMWorkerPool,
    ORMWorkerPoolQueue,
)

# -----------------------------------------------------
# --
# --
# -- Worker Pools
# --
# --
# -----------------------------------------------------


@inject_db
async def create_worker_pool(
    session: AsyncSession,
    worker_pool: schemas.core.WorkerPool,
    db: OrionDBInterface,
) -> ORMWorkerPool:
    """
    Creates a worker pool.

    If a WorkerPool with the same name exists, an error will be thrown.

    Args:
        session (AsyncSession): a database session
        worker_pool (schemas.core.WorkerPool): a WorkerPool model

    Returns:
        db.WorkerPool: the newly-created WorkerPool

    """

    pool = db.WorkerPool(**worker_pool.dict())
    session.add(pool)
    await session.flush()

    default_queue = await create_worker_pool_queue(
        session=session,
        worker_pool_id=pool.id,
        worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(
            name="Default Queue", description="The worker pool's default queue."
        ),
    )

    pool.default_queue_id = default_queue.id
    await session.flush()

    return pool


@inject_db
async def read_worker_pool(
    session: AsyncSession, worker_pool_id: UUID, db: OrionDBInterface
) -> ORMWorkerPool:
    """
    Reads a WorkerPool by id.

    Args:
        session (AsyncSession): A database session
        worker_pool_id (UUID): a WorkerPool id

    Returns:
        db.WorkerPool: the WorkerPool
    """
    query = sa.select(db.WorkerPool).where(db.WorkerPool.id == worker_pool_id).limit(1)
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_worker_pool_by_name(
    session: AsyncSession, worker_pool_name: str, db: OrionDBInterface
) -> ORMWorkerPool:
    """
    Reads a WorkerPool by name.

    Args:
        session (AsyncSession): A database session
        worker_pool_name (str): a WorkerPool name

    Returns:
        db.WorkerPool: the WorkerPool
    """
    query = (
        sa.select(db.WorkerPool).where(db.WorkerPool.name == worker_pool_name).limit(1)
    )
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_worker_pools(
    db: OrionDBInterface,
    session: AsyncSession,
    worker_pool_filter: schemas.filters.WorkerPoolFilter = None,
    offset: int = None,
    limit: int = None,
) -> List[ORMWorkerPool]:
    """
    Read worker configs.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
    Returns:
        List[db.WorkerPool]: worker configs
    """

    query = select(db.WorkerPool).order_by(db.WorkerPool.name)

    if worker_pool_filter is not None:
        query = query.where(worker_pool_filter.as_sql_filter(db))
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_worker_pool(
    session: AsyncSession,
    worker_pool_id: UUID,
    worker_pool: schemas.actions.WorkerPoolUpdate,
    db: OrionDBInterface,
) -> bool:
    """
    Update a WorkerPool by id.

    Args:
        session (AsyncSession): A database session
        worker_pool_id (UUID): a WorkerPool id
        worker: the work queue data

    Returns:
        bool: whether or not the worker was updated
    """
    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = worker_pool.dict(shallow=True, exclude_unset=True)

    update_stmt = (
        sa.update(db.WorkerPool)
        .where(db.WorkerPool.id == worker_pool_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)
    return result.rowcount > 0


@inject_db
async def delete_worker_pool(
    session: AsyncSession, worker_pool_id: UUID, db: OrionDBInterface
) -> bool:
    """
    Delete a WorkerPool by id.

    Args:
        session (AsyncSession): A database session
        worker_pool_id (UUID): a worker pool id

    Returns:
        bool: whether or not the WorkerPool was deleted
    """

    result = await session.execute(
        delete(db.WorkerPool).where(db.WorkerPool.id == worker_pool_id)
    )
    return result.rowcount > 0


@inject_db
async def get_scheduled_flow_runs(
    session: AsyncSession,
    worker_pool_ids: List[UUID] = None,
    worker_pool_queue_ids: List[UUID] = None,
    scheduled_before: datetime.datetime = None,
    scheduled_after: datetime.datetime = None,
    limit: int = None,
    respect_queue_priorities: bool = None,
    db: OrionDBInterface = None,
) -> List[schemas.responses.WorkerFlowRunResponse]:
    """
    Get runs from queues in a specific worker pool.

    Args:
        session (AsyncSession): a database session
        worker_pool_ids (List[UUID]): a list of worker pool ids
        worker_pool_queue_ids (List[UUID]): a list of worker pool queue ids
        scheduled_before (datetime.datetime): a datetime to filter runs scheduled before
        scheduled_after (datetime.datetime): a datetime to filter runs scheduled after
        respect_queue_priorities (bool): whether or not to respect queue priorities
        limit (int): the maximum number of runs to return
        db (OrionDBInterface): a database interface

    Returns:
        List[WorkerFlowRunResponse]: the runs, as well as related worker pool details

    """

    if respect_queue_priorities is None:
        respect_queue_priorities = True

    return await db.queries.get_scheduled_flow_runs_from_worker_pool(
        session=session,
        db=db,
        worker_pool_ids=worker_pool_ids,
        worker_pool_queue_ids=worker_pool_queue_ids,
        scheduled_before=scheduled_before,
        scheduled_after=scheduled_after,
        respect_queue_priorities=respect_queue_priorities,
        limit=limit,
    )


# -----------------------------------------------------
# --
# --
# -- worker pool queues
# --
# --
# -----------------------------------------------------


@inject_db
async def create_worker_pool_queue(
    session: AsyncSession,
    worker_pool_id: UUID,
    worker_pool_queue: schemas.actions.WorkerPoolQueueCreate,
    db: OrionDBInterface,
) -> ORMWorkerPoolQueue:
    """
    Creates a worker pool queue.

    Args:
        session (AsyncSession): a database session
        worker_pool_id (UUID): a worker pool id
        worker_pool_queue (schemas.actions.WorkerPoolQueueCreate): a WorkerPoolQueue action model

    Returns:
        db.WorkerPoolQueue: the newly-created WorkerPoolQueue

    """

    max_priority_query = sa.select(
        sa.func.coalesce(sa.func.max(db.WorkerPoolQueue.priority), 0)
    ).where(db.WorkerPoolQueue.worker_pool_id == worker_pool_id)
    priority = (await session.execute(max_priority_query)).scalar()

    model = db.WorkerPoolQueue(
        **worker_pool_queue.dict(exclude={"priority"}),
        worker_pool_id=worker_pool_id,
        # initialize the priority as the current max priority + 1
        priority=priority + 1
    )

    session.add(model)
    await session.flush()

    if worker_pool_queue.priority:
        await bulk_update_worker_pool_queue_priorities(
            session=session,
            worker_pool_id=worker_pool_id,
            new_priorities={model.id: worker_pool_queue.priority},
            db=db,
        )
    return model


@inject_db
async def bulk_update_worker_pool_queue_priorities(
    session: AsyncSession,
    worker_pool_id: UUID,
    new_priorities: Dict[UUID, int],
    db: OrionDBInterface,
):
    """
    This is a brute force update of all worker pool queue priorities for a given worker
    pool.

    It loads all queues fully into memory, sorts them, and flushes the update to
    the db.

    Updating queue priorities is not a common operation (happens on the same scale as
    queue modification, which is significantly less than reading from queues),
    so while this implementation is slow, it may suffice and make up for that
    with extreme simplicity.
    """

    if len(set(new_priorities.values())) != len(new_priorities):
        raise ValueError("Duplicate target priorities provided")

    worker_pool_queues_query = (
        sa.select(db.WorkerPoolQueue)
        .where(db.WorkerPoolQueue.worker_pool_id == worker_pool_id)
        .order_by(db.WorkerPoolQueue.priority.asc())
    )
    result = await session.execute(worker_pool_queues_query)
    all_worker_pool_queues = result.scalars().all()

    worker_pool_queues = [
        wq for wq in all_worker_pool_queues if wq.id not in new_priorities
    ]
    updated_queues = [wq for wq in all_worker_pool_queues if wq.id in new_priorities]

    for queue in sorted(updated_queues, key=lambda wq: new_priorities[wq.id]):
        worker_pool_queues.insert(new_priorities[queue.id] - 1, queue)

    for i, queue in enumerate(worker_pool_queues):
        queue.priority = i + 1

    await session.flush()


@inject_db
async def read_worker_pool_queues(
    session: AsyncSession,
    worker_pool_id: UUID,
    db: OrionDBInterface,
) -> List[ORMWorkerPoolQueue]:
    """
    Read all worker pool queues for a worker pool. Results are ordered by ascending priority.

    Args:
        session (AsyncSession): a database session
        worker_pool_id (UUID): a worker pool id

    Returns:
        List[db.WorkerPoolQueue]: the WorkerPoolQueues

    """
    query = (
        sa.select(db.WorkerPoolQueue)
        .where(db.WorkerPoolQueue.worker_pool_id == worker_pool_id)
        .order_by(db.WorkerPoolQueue.priority.asc())
    )
    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def read_worker_pool_queue(
    session: AsyncSession,
    worker_pool_queue_id: UUID,
    db: OrionDBInterface,
) -> ORMWorkerPoolQueue:
    """
    Read a specific worker pool queue.

    Args:
        session (AsyncSession): a database session
        worker_pool_queue_id (UUID): a worker pool queue id

    Returns:
        db.WorkerPoolQueue: the WorkerPoolQueue

    """
    return await session.get(db.WorkerPoolQueue, worker_pool_queue_id)


@inject_db
async def read_worker_pool_queue_by_name(
    session: AsyncSession,
    worker_pool_name: str,
    worker_pool_queue_name: str,
    db: OrionDBInterface,
) -> ORMWorkerPoolQueue:
    """
    Reads a WorkerPoolQueue by name.

    Args:
        session (AsyncSession): A database session
        worker_pool_name (str): a WorkerPool name
        worker_pool_queue_name (str): a WorkerPoolQueue name

    Returns:
        db.WorkerPoolQueue: the WorkerPoolQueue
    """
    query = (
        sa.select(db.WorkerPoolQueue)
        .join(db.WorkerPool, db.WorkerPool.id == db.WorkerPoolQueue.worker_pool_id)
        .where(
            db.WorkerPool.name == worker_pool_name,
            db.WorkerPoolQueue.name == worker_pool_queue_name,
        )
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def update_worker_pool_queue(
    session: AsyncSession,
    worker_pool_queue_id: UUID,
    worker_pool_queue: schemas.actions.WorkerPoolQueueUpdate,
    db: OrionDBInterface,
) -> bool:
    """
    Update a worker pool queue.

    Args:
        session (AsyncSession): a database session
        worker_pool_queue_id (UUID): a worker pool queue ID
        worker_pool_queue (schemas.actions.WorkerPoolQueueUpdate): a WorkerPoolQueue model

    Returns:
        bool: whether or not the WorkerPoolQueue was updated

    """
    update_values = worker_pool_queue.dict(shallow=True, exclude_unset=True)
    update_stmt = (
        sa.update(db.WorkerPoolQueue)
        .where(db.WorkerPoolQueue.id == worker_pool_queue_id)
        .values(update_values)
    )
    result = await session.execute(update_stmt)

    if result.rowcount > 0 and "priority" in update_values:
        worker_pool_queue = await session.get(db.WorkerPoolQueue, worker_pool_queue_id)
        await bulk_update_worker_pool_queue_priorities(
            session,
            worker_pool_id=worker_pool_queue.worker_pool_id,
            new_priorities={worker_pool_queue_id: update_values["priority"]},
        )
    return result.rowcount > 0


@inject_db
async def delete_worker_pool_queue(
    session: AsyncSession,
    worker_pool_queue_id: UUID,
    db: OrionDBInterface,
) -> bool:
    """
    Delete a worker pool queue.

    Args:
        session (AsyncSession): a database session
        worker_pool_queue_id (UUID): a worker pool queue ID

    Returns:
        bool: whether or not the WorkerPoolQueue was deleted

    """
    worker_pool_queue = await session.get(db.WorkerPoolQueue, worker_pool_queue_id)
    if worker_pool_queue is None:
        return False

    await session.delete(worker_pool_queue)
    try:
        await session.flush()

    # if an error was raised, check if the user tried to delete a default queue
    except sa.exc.IntegrityError as exc:
        if "foreign key constraint" in str(exc).lower():
            raise ValueError("Can't delete a pool's default queue.")
        raise

    await bulk_update_worker_pool_queue_priorities(
        session,
        worker_pool_id=worker_pool_queue.worker_pool_id,
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
    worker_pool_id: UUID,
    worker_filter: schemas.filters.WorkerFilter = None,
    limit: int = None,
    offset: int = None,
    db: OrionDBInterface = None,
) -> List[ORMWorker]:

    query = (
        sa.select(db.Worker)
        .where(db.Worker.worker_pool_id == worker_pool_id)
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
    worker_pool_id: UUID,
    worker_name: str,
    db: OrionDBInterface,
) -> bool:
    """
    Record a worker process heartbeat.

    Args:
        session (AsyncSession): a database session
        worker_pool_id (UUID): a worker pool ID
        worker_name (str): a worker name

    Returns:
        bool: whether or not the worker was updated

    """
    now = pendulum.now("UTC")
    insert_stmt = (
        (await db.insert(db.Worker))
        .values(
            worker_pool_id=worker_pool_id,
            name=worker_name,
            last_heartbeat_time=now,
        )
        .on_conflict_do_update(
            index_elements=[
                db.Worker.worker_pool_id,
                db.Worker.name,
            ],
            set_=dict(last_heartbeat_time=now),
        )
    )

    result = await session.execute(insert_stmt)
    return result.rowcount > 0
