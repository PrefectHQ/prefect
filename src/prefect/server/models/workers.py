"""
Functions for interacting with worker ORM objects.
Intended for internal use by the Prefect REST API.
"""

import datetime
from typing import (
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Union,
)
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect._internal.uuid7 import uuid7
from prefect.server.database import PrefectDBInterface, db_injector, orm_models
from prefect.server.events.clients import PrefectServerEventsClient
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.models.events import work_pool_status_event
from prefect.server.schemas.statuses import WorkQueueStatus
from prefect.server.utilities.database import UUID as PrefectUUID
from prefect.types._datetime import DateTime, now

DEFAULT_AGENT_WORK_POOL_NAME = "default-agent-pool"

# -----------------------------------------------------
# --
# --
# -- Work Pools
# --
# --
# -----------------------------------------------------


@db_injector
async def create_work_pool(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool: Union[schemas.core.WorkPool, schemas.actions.WorkPoolCreate],
) -> orm_models.WorkPool:
    """
    Creates a work pool.

    If a WorkPool with the same name exists, an error will be thrown.

    Args:
        session (AsyncSession): a database session
        work_pool (schemas.core.WorkPool): a WorkPool model

    Returns:
        orm_models.WorkPool: the newly-created WorkPool

    """

    pool = db.WorkPool(**work_pool.model_dump())

    if pool.type != "prefect-agent":
        if pool.is_paused:
            pool.status = schemas.statuses.WorkPoolStatus.PAUSED
        else:
            pool.status = schemas.statuses.WorkPoolStatus.NOT_READY

    session.add(pool)
    await session.flush()

    default_queue = await create_work_queue(
        session=session,
        work_pool_id=pool.id,
        work_queue=schemas.actions.WorkQueueCreate(
            name="default", description="The work pool's default queue."
        ),
    )

    pool.default_queue_id = default_queue.id  # type: ignore
    await session.flush()

    return pool


@db_injector
async def read_work_pool(
    db: PrefectDBInterface, session: AsyncSession, work_pool_id: UUID
) -> Optional[orm_models.WorkPool]:
    """
    Reads a WorkPool by id.

    Args:
        session (AsyncSession): A database session
        work_pool_id (UUID): a WorkPool id

    Returns:
        orm_models.WorkPool: the WorkPool
    """
    query = sa.select(db.WorkPool).where(db.WorkPool.id == work_pool_id).limit(1)
    result = await session.execute(query)
    return result.scalar()


@db_injector
async def read_work_pool_by_name(
    db: PrefectDBInterface, session: AsyncSession, work_pool_name: str
) -> Optional[orm_models.WorkPool]:
    """
    Reads a WorkPool by name.

    Args:
        session (AsyncSession): A database session
        work_pool_name (str): a WorkPool name

    Returns:
        orm_models.WorkPool: the WorkPool
    """
    query = sa.select(db.WorkPool).where(db.WorkPool.name == work_pool_name).limit(1)
    result = await session.execute(query)
    return result.scalar()


@db_injector
async def read_work_pools(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_filter: Optional[schemas.filters.WorkPoolFilter] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Sequence[orm_models.WorkPool]:
    """
    Read worker configs.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
    Returns:
        List[orm_models.WorkPool]: worker configs
    """

    query = select(db.WorkPool).order_by(db.WorkPool.name)

    if work_pool_filter is not None:
        query = query.where(work_pool_filter.as_sql_filter())
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def count_work_pools(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_filter: Optional[schemas.filters.WorkPoolFilter] = None,
) -> int:
    """
    Read worker configs.

    Args:
        session: A database session
        work_pool_filter: filter criteria to apply to the count
    Returns:
        int: the count of work pools matching the criteria
    """

    query = select(sa.func.count()).select_from(db.WorkPool)

    if work_pool_filter is not None:
        query = query.where(work_pool_filter.as_sql_filter())

    result = await session.execute(query)
    return result.scalar_one()


@db_injector
async def update_work_pool(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_id: UUID,
    work_pool: schemas.actions.WorkPoolUpdate,
    emit_status_change: Optional[
        Callable[
            [UUID, DateTime, orm_models.WorkPool, orm_models.WorkPool],
            Awaitable[None],
        ]
    ] = None,
) -> bool:
    """
    Update a WorkPool by id.

    Args:
        session (AsyncSession): A database session
        work_pool_id (UUID): a WorkPool id
        worker: the work queue data
        emit_status_change: function to call when work pool
            status is changed

    Returns:
        bool: whether or not the worker was updated
    """
    # exclude_unset=True allows us to only update values provided by
    # the user, ignoring any defaults on the model
    update_data = work_pool.model_dump_for_orm(exclude_unset=True)

    current_work_pool = await read_work_pool(session=session, work_pool_id=work_pool_id)
    if not current_work_pool:
        raise ObjectNotFoundError

    # Remove this from the session so we have a copy of the current state before we
    # update it; this will give us something to compare against when emitting events
    session.expunge(current_work_pool)

    if current_work_pool.type != "prefect-agent":
        if update_data.get("is_paused"):
            update_data["status"] = schemas.statuses.WorkPoolStatus.PAUSED

        if update_data.get("is_paused") is False:
            # If the work pool has any online workers, set the status to READY
            # Otherwise set it to, NOT_READY
            workers = await read_workers(
                session=session,
                work_pool_id=work_pool_id,
                worker_filter=schemas.filters.WorkerFilter(
                    status=schemas.filters.WorkerFilterStatus(
                        any_=[schemas.statuses.WorkerStatus.ONLINE]
                    )
                ),
            )
            if len(workers) > 0:
                update_data["status"] = schemas.statuses.WorkPoolStatus.READY
            else:
                update_data["status"] = schemas.statuses.WorkPoolStatus.NOT_READY

    if "status" in update_data:
        update_data["last_status_event_id"] = uuid7()
        update_data["last_transitioned_status_at"] = now("UTC")

    update_stmt = (
        sa.update(db.WorkPool)
        .where(db.WorkPool.id == work_pool_id)
        .values(**update_data)
    )
    result = await session.execute(update_stmt)

    updated = result.rowcount > 0
    if updated:
        wp = await read_work_pool(session=session, work_pool_id=work_pool_id)

        assert wp is not None
        assert current_work_pool is not wp

        if "status" in update_data and emit_status_change:
            await emit_status_change(
                event_id=update_data["last_status_event_id"],  # type: ignore
                occurred=update_data["last_transitioned_status_at"],
                pre_update_work_pool=current_work_pool,
                work_pool=wp,
            )

    return updated


@db_injector
async def delete_work_pool(
    db: PrefectDBInterface, session: AsyncSession, work_pool_id: UUID
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


@db_injector
async def get_scheduled_flow_runs(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_ids: Optional[List[UUID]] = None,
    work_queue_ids: Optional[List[UUID]] = None,
    scheduled_before: Optional[datetime.datetime] = None,
    scheduled_after: Optional[datetime.datetime] = None,
    limit: Optional[int] = None,
    respect_queue_priorities: Optional[bool] = None,
) -> Sequence[schemas.responses.WorkerFlowRunResponse]:
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


@db_injector
async def create_work_queue(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_id: UUID,
    work_queue: schemas.actions.WorkQueueCreate,
) -> orm_models.WorkQueue:
    """
    Creates a work pool queue.

    Args:
        session (AsyncSession): a database session
        work_pool_id (UUID): a work pool id
        work_queue (schemas.actions.WorkQueueCreate): a WorkQueue action model

    Returns:
        orm_models.WorkQueue: the newly-created WorkQueue

    """
    data = work_queue.model_dump(exclude={"work_pool_id"})
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
        )
    return model


@db_injector
async def bulk_update_work_queue_priorities(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_id: UUID,
    new_priorities: Dict[UUID, int],
) -> None:
    """
    This is a brute force update of all work pool queue priorities for a given work
    pool.

    It loads all queues fully into memory, sorts them, and flushes the update to
    the orm_models. The algorithm ensures that priorities are unique integers > 0, and
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


@db_injector
async def read_work_queues(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_id: UUID,
    work_queue_filter: Optional[schemas.filters.WorkQueueFilter] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Sequence[orm_models.WorkQueue]:
    """
    Read all work pool queues for a work pool. Results are ordered by ascending priority.

    Args:
        session (AsyncSession): a database session
        work_pool_id (UUID): a work pool id
        work_queue_filter: Filter criteria for work pool queues
        offset: Query offset
        limit: Query limit


    Returns:
        List[orm_models.WorkQueue]: the WorkQueues

    """
    query = (
        sa.select(db.WorkQueue)
        .where(db.WorkQueue.work_pool_id == work_pool_id)
        .order_by(db.WorkQueue.priority.asc())
    )

    if work_queue_filter is not None:
        query = query.where(work_queue_filter.as_sql_filter())
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@db_injector
async def read_work_queue(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_queue_id: Union[UUID, PrefectUUID],
) -> Optional[orm_models.WorkQueue]:
    """
    Read a specific work pool queue.

    Args:
        session (AsyncSession): a database session
        work_queue_id (UUID): a work pool queue id

    Returns:
        orm_models.WorkQueue: the WorkQueue

    """
    return await session.get(db.WorkQueue, work_queue_id)


@db_injector
async def read_work_queue_by_name(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_name: str,
    work_queue_name: str,
) -> Optional[orm_models.WorkQueue]:
    """
    Reads a WorkQueue by name.

    Args:
        session (AsyncSession): A database session
        work_pool_name (str): a WorkPool name
        work_queue_name (str): a WorkQueue name

    Returns:
        orm_models.WorkQueue: the WorkQueue
    """
    query = (
        sa.select(db.WorkQueue)
        .join(
            db.WorkPool,
            db.WorkPool.id == db.WorkQueue.work_pool_id,
        )
        .where(
            db.WorkPool.name == work_pool_name,
            db.WorkQueue.name == work_queue_name,
        )
        .limit(1)
    )
    result = await session.execute(query)
    return result.scalar()


@db_injector
async def update_work_queue(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_queue_id: UUID,
    work_queue: schemas.actions.WorkQueueUpdate,
    emit_status_change: Optional[
        Callable[[orm_models.WorkQueue], Awaitable[None]]
    ] = None,
    default_status: WorkQueueStatus = WorkQueueStatus.NOT_READY,
) -> bool:
    """
    Update a work pool queue.

    Args:
        session (AsyncSession): a database session
        work_queue_id (UUID): a work pool queue ID
        work_queue (schemas.actions.WorkQueueUpdate): a WorkQueue model
        emit_status_change: function to call when work queue
            status is changed

    Returns:
        bool: whether or not the WorkQueue was updated

    """
    from prefect.server.models.work_queues import is_last_polled_recent

    update_values = work_queue.model_dump_for_orm(exclude_unset=True)

    if "is_paused" in update_values:
        if (wq := await session.get(db.WorkQueue, work_queue_id)) is None:
            return False

        # Only update the status to paused if it's not already paused. This ensures a work queue that is already
        # paused will not get a status update if it's paused again
        if update_values.get("is_paused") and wq.status != WorkQueueStatus.PAUSED:
            update_values["status"] = WorkQueueStatus.PAUSED

        # If unpausing, only update status if it's currently paused. This ensures a work queue that is already
        # unpaused will not get a status update if it's unpaused again
        if (
            update_values.get("is_paused") is False
            and wq.status == WorkQueueStatus.PAUSED
        ):
            # Default status if unpaused
            update_values["status"] = default_status

            # Determine source of last_polled: update_data or database
            if "last_polled" in update_values:
                last_polled = update_values["last_polled"]
            else:
                last_polled = wq.last_polled

            # Check if last polled is recent and set status to READY if so
            if is_last_polled_recent(last_polled):
                update_values["status"] = schemas.statuses.WorkQueueStatus.READY

    update_stmt = (
        sa.update(db.WorkQueue)
        .where(db.WorkQueue.id == work_queue_id)
        .values(update_values)
    )
    result = await session.execute(update_stmt)

    updated = result.rowcount > 0

    if updated:
        if "priority" in update_values or "status" in update_values:
            updated_work_queue = await session.get(db.WorkQueue, work_queue_id)
            assert updated_work_queue

            if "priority" in update_values:
                await bulk_update_work_queue_priorities(
                    session,
                    work_pool_id=updated_work_queue.work_pool_id,
                    new_priorities={work_queue_id: update_values["priority"]},
                )

            if "status" in update_values and emit_status_change:
                await emit_status_change(updated_work_queue)

    return updated


@db_injector
async def delete_work_queue(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_queue_id: UUID,
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


@db_injector
async def read_workers(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_id: UUID,
    worker_filter: Optional[schemas.filters.WorkerFilter] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> Sequence[orm_models.Worker]:
    query = (
        sa.select(db.Worker)
        .where(db.Worker.work_pool_id == work_pool_id)
        .order_by(db.Worker.last_heartbeat_time.desc())
        .limit(limit)
    )

    if worker_filter:
        query = query.where(worker_filter.as_sql_filter())

    if limit is not None:
        query = query.limit(limit)

    if offset is not None:
        query = query.offset(offset)

    result = await session.execute(query)
    return result.scalars().all()


@db_injector
async def worker_heartbeat(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_id: UUID,
    worker_name: str,
    heartbeat_interval_seconds: Optional[int] = None,
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
    right_now = now("UTC")
    # Values that won't change between heart beats
    base_values = dict(
        work_pool_id=work_pool_id,
        name=worker_name,
    )
    # Values that can and will change between heartbeats
    update_values = dict(
        last_heartbeat_time=right_now,
        status=schemas.statuses.WorkerStatus.ONLINE,
    )
    if heartbeat_interval_seconds is not None:
        update_values["heartbeat_interval_seconds"] = heartbeat_interval_seconds

    insert_stmt = (
        db.queries.insert(db.Worker)
        .values(**base_values, **update_values)
        .on_conflict_do_update(
            index_elements=[
                db.Worker.work_pool_id,
                db.Worker.name,
            ],
            set_=update_values,
        )
    )

    result = await session.execute(insert_stmt)
    return result.rowcount > 0


@db_injector
async def delete_worker(
    db: PrefectDBInterface,
    session: AsyncSession,
    work_pool_id: UUID,
    worker_name: str,
) -> bool:
    """
    Delete a work pool's worker.

    Args:
        session (AsyncSession): a database session
        work_pool_id (UUID): a work pool ID
        worker_name (str): a worker name

    Returns:
        bool: whether or not the Worker was deleted

    """
    result = await session.execute(
        delete(db.Worker).where(
            db.Worker.work_pool_id == work_pool_id,
            db.Worker.name == worker_name,
        )
    )

    return result.rowcount > 0


async def emit_work_pool_status_event(
    event_id: UUID,
    occurred: DateTime,
    pre_update_work_pool: Optional[orm_models.WorkPool],
    work_pool: orm_models.WorkPool,
) -> None:
    if not work_pool.status:
        return

    async with PrefectServerEventsClient() as events_client:
        await events_client.emit(
            await work_pool_status_event(
                event_id=event_id,
                occurred=occurred,
                pre_update_work_pool=pre_update_work_pool,
                work_pool=work_pool,
            )
        )
