"""
Functions for interacting with work queue ORM objects.
Intended for internal use by the Prefect REST API.
"""

import datetime
from uuid import UUID

import sqlalchemy as sa
from pydantic import parse_obj_as
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.models.workers import (
    DEFAULT_AGENT_WORK_POOL_NAME,
    bulk_update_work_queue_priorities,
)
from prefect.server.schemas.states import StateType


@inject_db
async def create_work_queue(
    session: AsyncSession,
    work_queue: schemas.core.WorkQueue,
    db: PrefectDBInterface,
):
    """
    Inserts a WorkQueue.

    If a WorkQueue with the same name exists, an error will be thrown.

    Args:
        session (AsyncSession): a database session
        work_queue (schemas.core.WorkQueue): a WorkQueue model

    Returns:
        db.WorkQueue: the newly-created or updated WorkQueue

    """
    data = work_queue.dict()

    if data.get("work_pool_id") is None:
        # If no work pool is provided, get or create the default agent work pool
        default_agent_work_pool = await models.workers.read_work_pool_by_name(
            session=session, work_pool_name=DEFAULT_AGENT_WORK_POOL_NAME
        )
        if default_agent_work_pool:
            data["work_pool_id"] = default_agent_work_pool.id
        else:
            default_agent_work_pool = await models.workers.create_work_pool(
                session=session,
                work_pool=schemas.actions.WorkPoolCreate(
                    name=DEFAULT_AGENT_WORK_POOL_NAME, type="prefect-agent"
                ),
            )
            if work_queue.name == "default":
                # If the desired work queue name is default, it was created when the
                # work pool was created. We can just return it.
                return await models.workers.read_work_queue(
                    session=session,
                    work_queue_id=default_agent_work_pool.default_queue_id,
                )
            data["work_pool_id"] = default_agent_work_pool.id

    # Set the priority to be the max priority + 1
    # This will make the new queue the lowest priority
    if data["priority"] is None:
        # Set the priority to be the first priority value that isn't already taken
        priorities_query = sa.select(db.WorkQueue.priority).where(
            db.WorkQueue.work_pool_id == data["work_pool_id"]
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

    model = db.WorkQueue(**data)

    session.add(model)
    await session.flush()
    await session.refresh(model)

    if work_queue.priority:
        await bulk_update_work_queue_priorities(
            session=session,
            work_pool_id=data["work_pool_id"],
            new_priorities={model.id: work_queue.priority},
            db=db,
        )

    return model


@inject_db
async def read_work_queue(
    session: AsyncSession, work_queue_id: UUID, db: PrefectDBInterface
):
    """
    Reads a WorkQueue by id.

    Args:
        session (AsyncSession): A database session
        work_queue_id (str): a WorkQueue id

    Returns:
        db.WorkQueue: the WorkQueue
    """

    return await session.get(db.WorkQueue, work_queue_id)


@inject_db
async def read_work_queue_by_name(
    session: AsyncSession, name: str, db: PrefectDBInterface
):
    """
    Reads a WorkQueue by id.

    Args:
        session (AsyncSession): A database session
        work_queue_id (str): a WorkQueue id

    Returns:
        db.WorkQueue: the WorkQueue
    """
    default_work_pool = await models.workers.read_work_pool_by_name(
        session=session, work_pool_name=DEFAULT_AGENT_WORK_POOL_NAME
    )
    # Logic to make sure this functionality doesn't break during migration
    if default_work_pool is not None:
        query = select(db.WorkQueue).filter_by(
            name=name, work_pool_id=default_work_pool.id
        )
    else:
        query = select(db.WorkQueue).filter_by(name=name)
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_work_queues(
    db: PrefectDBInterface,
    session: AsyncSession,
    offset: int = None,
    limit: int = None,
    work_queue_filter: schemas.filters.WorkQueueFilter = None,
):
    """
    Read WorkQueues.

    Args:
        session: A database session
        offset: Query offset
        limit: Query limit
        work_queue_filter: only select work queues matching these filters
    Returns:
        List[db.WorkQueue]: WorkQueues
    """

    query = select(db.WorkQueue).order_by(db.WorkQueue.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    if work_queue_filter:
        query = query.where(work_queue_filter.as_sql_filter(db))

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_work_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    work_queue: schemas.actions.WorkQueueUpdate,
    db: PrefectDBInterface,
) -> bool:
    """
    Update a WorkQueue by id.

    Args:
        session (AsyncSession): A database session
        work_queue: the work queue data
        work_queue_id (str): a WorkQueue id

    Returns:
        bool: whether or not the WorkQueue was updated
    """
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
    session: AsyncSession, work_queue_id: UUID, db: PrefectDBInterface
) -> bool:
    """
    Delete a WorkQueue by id.

    Args:
        session (AsyncSession): A database session
        work_queue_id (str): a WorkQueue id

    Returns:
        bool: whether or not the WorkQueue was deleted
    """
    result = await session.execute(
        delete(db.WorkQueue).where(db.WorkQueue.id == work_queue_id)
    )

    return result.rowcount > 0


@inject_db
async def get_runs_in_work_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    db: PrefectDBInterface,
    limit: int = None,
    scheduled_before: datetime.datetime = None,
):
    """
    Get runs from a work queue.

    Args:
        session: A database session. work_queue_id: The work queue id.
        scheduled_before: Only return runs scheduled to start before this time.
        limit: An optional limit for the number of runs to return from the
            queue. This limit applies to the request only. It does not affect
            the work queue's concurrency limit. If `limit` exceeds the work
            queue's concurrency limit, it will be ignored.

    """
    work_queue = await read_work_queue(session=session, work_queue_id=work_queue_id)
    if not work_queue:
        raise ObjectNotFoundError(f"Work queue with id {work_queue_id} not found.")

    if work_queue.filter is None:
        query = db.queries.get_scheduled_flow_runs_from_work_queues(
            db=db,
            limit_per_queue=limit,
            work_queue_ids=[work_queue_id],
            scheduled_before=scheduled_before,
        )
        result = await session.execute(query)
        return result.scalars().unique().all()

    # if the work queue has a filter, it's a deprecated tag-based work queue
    # and uses an old approach
    else:
        return await _legacy_get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue_id,
            db=db,
            scheduled_before=scheduled_before,
            limit=limit,
        )


@inject_db
async def _legacy_get_runs_in_work_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    db: PrefectDBInterface,
    scheduled_before: datetime.datetime = None,
    limit: int = None,
):
    """
    DEPRECATED method for getting runs from a tag-based work queue

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
    flow_run_filter = dict(
        tags=dict(all_=work_queue_filter.tags),
        deployment_id=dict(any_=work_queue_filter.deployment_ids, is_null_=False),
    )

    # if the work queue has a concurrency limit, check how many runs are currently
    # executing and compare that count to the concurrency limit
    if work_queue.concurrency_limit is not None:
        # Note this does not guarantee race conditions wont be hit
        running_frs = await models.flow_runs.count_flow_runs(
            session=session,
            flow_run_filter=schemas.filters.FlowRunFilter(
                **flow_run_filter,
                state=dict(type=dict(any_=[StateType.PENDING, StateType.RUNNING])),
            ),
        )

        # compute the available concurrency slots
        open_concurrency_slots = max(0, work_queue.concurrency_limit - running_frs)

        # if a limit override was given, ensure we return no more
        # than that limit
        if limit is not None:
            limit = min(open_concurrency_slots, limit)
        else:
            limit = open_concurrency_slots

    return await models.flow_runs.read_flow_runs(
        session=session,
        flow_run_filter=schemas.filters.FlowRunFilter(
            **flow_run_filter,
            state=dict(type=dict(any_=[StateType.SCHEDULED])),
            next_scheduled_start_time=dict(before_=scheduled_before),
        ),
        limit=limit,
        sort=schemas.sorting.FlowRunSort.NEXT_SCHEDULED_START_TIME_ASC,
    )


@inject_db
async def _ensure_work_queue_exists(
    session: AsyncSession, name: str, db: PrefectDBInterface
):
    """
    Checks if a work queue exists and creates it if it does not.

    Useful when working with deployments, agents, and flow runs that automatically create work queues.

    Will also create a work pool queue in the default agent pool to facilitate migration to work pools.
    """
    # read work queue
    work_queue = await models.work_queues.read_work_queue_by_name(
        session=session, name=name
    )
    if not work_queue:
        default_pool = await models.workers.read_work_pool_by_name(
            session=session, work_pool_name=DEFAULT_AGENT_WORK_POOL_NAME
        )

        if default_pool is None:
            work_queue = await models.work_queues.create_work_queue(
                session=session,
                work_queue=schemas.actions.WorkQueueCreate(name=name, priority=1),
            )
        else:
            if name != "default":
                work_queue = await models.workers.create_work_queue(
                    session=session,
                    work_pool_id=default_pool.id,
                    work_queue=schemas.actions.WorkQueueCreate(name=name, priority=1),
                )
            else:
                work_queue = await models.work_queues.read_work_queue(
                    session=session, work_queue_id=default_pool.default_queue_id
                )

    return work_queue


@inject_db
async def read_work_queue_status(
    session: AsyncSession, work_queue_id: UUID, db: PrefectDBInterface
) -> schemas.core.WorkQueueStatusDetail:
    """
    Get work queue status by id.

    Args:
        session (AsyncSession): A database session
        work_queue_id (str): a WorkQueue id

    Returns:
        Information about the status of the work queue.
    """

    work_queue = await read_work_queue(session=session, work_queue_id=work_queue_id)
    if not work_queue:
        raise ObjectNotFoundError(f"Work queue with id {work_queue_id} not found")

    work_queue_late_runs_count = await models.flow_runs.count_flow_runs(
        session=session,
        flow_run_filter=schemas.filters.FlowRunFilter(
            state=schemas.filters.FlowRunFilterState(name={"any_": ["Late"]}),
        ),
        work_queue_filter=schemas.filters.WorkQueueFilter(
            id=schemas.filters.WorkQueueFilterId(any_=[work_queue_id])
        ),
    )

    # All work queues use the default policy for now
    health_check_policy = schemas.core.WorkQueueHealthPolicy(
        maximum_late_runs=0, maximum_seconds_since_last_polled=60
    )

    healthy = health_check_policy.evaluate_health_status(
        late_runs_count=work_queue_late_runs_count,
        last_polled=work_queue.last_polled,
    )

    return schemas.core.WorkQueueStatusDetail(
        healthy=healthy,
        late_runs_count=work_queue_late_runs_count,
        last_polled=work_queue.last_polled,
        health_check_policy=health_check_policy,
    )
