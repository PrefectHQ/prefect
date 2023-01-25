"""
Utility functions for migrating from work queues to work pools
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.orion import models, schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.utilities.schemas import DateTimeTZ

DEFAULT_AGENT_WORK_POOL_NAME = "default-agent-pool"
PREFECT_AGENT_WORK_POOL_TYPE = "prefect-agent"


@inject_db
async def get_or_create_default_agent_work_pool(
    session: AsyncSession, db: OrionDBInterface = None
):
    """
    Gets or creates the default work pool for agents.

    Args:
        session (AsyncSession): a database session

    Returns:
        db.WorkPool: The default agents work pool
    """
    pool = await models.workers.read_work_pool_by_name(
        session=session, work_pool_name=DEFAULT_AGENT_WORK_POOL_NAME
    )
    if pool is None:
        pool = await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name=DEFAULT_AGENT_WORK_POOL_NAME,
                description="A default work pool for Prefect Agents",
                type=PREFECT_AGENT_WORK_POOL_TYPE,
            ),
        )
    return pool


@inject_db
async def get_or_create_work_pool_queue(
    session: AsyncSession,
    work_queue_id: Optional[UUID] = None,
    work_queue_name: Optional[str] = None,
    db: OrionDBInterface = None,
):
    """
    Gets or creates a work pool queue for a work queue.

    Will update corresponding deployments and flow runs to point at the new work pool queue.

    Args:
        session (AsyncSession): a database session
        work_queue_id (UUID): the work queue id
        work_queue_name (str): the work queue name
        db (OrionDBInterface, optional): a database interface. Defaults to None.

    Returns:
        db.WorkPoolQueue: The work pool queue
    """

    if (work_queue_id, work_queue_name) == (None, None):
        raise ValueError(
            "Either the work queue name or the work queue ID must be provided."
        )

    if work_queue_id is not None:
        work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )
    else:
        work_queue = await models.work_queues.read_work_queue_by_name(
            session=session, name=work_queue_name
        )

    if not work_queue:
        raise ObjectNotFoundError()

    # get or create the default agents pool
    pool = await get_or_create_default_agent_work_pool(session=session, db=db)

    # get or create the work pool queue
    work_pool_queue = await models.workers.read_work_pool_queue_by_name(
        session=session,
        work_pool_name=DEFAULT_AGENT_WORK_POOL_NAME,
        work_pool_queue_name=work_queue.name,
    )
    if work_pool_queue is None:
        work_pool_queue = await models.workers.create_work_pool_queue(
            session=session,
            work_pool_id=pool.id,
            work_pool_queue=schemas.actions.WorkPoolQueueCreate(
                name=work_queue.name,
                description=work_queue.description,
                is_paused=work_queue.is_paused,
                concurrency_limit=work_queue.concurrency_limit,
            ),
        )

        # update deployments to point at the new work queue
        update_deployments_stmt = (
            sa.update(db.Deployment)
            .where(
                db.Deployment.work_queue_name == work_queue.name,
                db.Deployment.work_pool_queue_id.is_(None),
            )
            .values(work_pool_queue_id=work_pool_queue.id)
        )
        await session.execute(update_deployments_stmt)

        # update scheduled flow runs to point at the new work queue
        offset = 0
        while True:
            where_clause = (
                sa.select([db.FlowRun.id])
                .where(
                    db.FlowRun.work_queue_name == work_queue.name,
                    db.FlowRun.state_type == "SCHEDULED",
                    db.FlowRun.work_pool_queue_id.is_(None),
                )
                .order_by(db.FlowRun.id.asc())
                .limit(50)
                .offset(offset)
            )
            result = await session.execute(where_clause)
            flow_run_ids = result.scalars().all()

            if not flow_run_ids:
                break

            update_flow_runs_stmt = (
                sa.update(db.FlowRun)
                .where(
                    db.FlowRun.id.in_(flow_run_ids),
                )
                .values(work_pool_queue_id=work_pool_queue.id)
            )
            await session.execute(update_flow_runs_stmt)
            await session.commit()
            offset += 50

    # return the new queue
    return work_pool_queue


@inject_db
async def get_runs_from_work_pool_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    scheduled_before: Optional[DateTimeTZ] = None,
    limit: Optional[int] = None,
    db: Optional[OrionDBInterface] = None,
):
    work_pool_queue = await get_or_create_work_pool_queue(
        session=session, work_queue_id=work_queue_id, db=db
    )

    return await models.workers.get_scheduled_flow_runs(
        session=session,
        work_pool_ids=[work_pool_queue.work_pool_id],
        work_pool_queue_ids=[work_pool_queue.id],
        scheduled_before=scheduled_before,
        limit=limit,
        db=db,
    )


@inject_db
async def migrate_all_work_queues(
    session: AsyncSession,
    db: Optional[OrionDBInterface] = None,
):
    """
    Migrates all existing work queues to the default Prefect agent work pool.

    Can be run at any time to facilitate user-initiated migrations without
    waiting for an agent to poll.
    """
    offset = 0
    while True:
        work_queues = await models.work_queues.read_work_queues(
            session=session, offset=offset, limit=25
        )
        if not work_queues:
            break

        for work_queue in work_queues:
            await get_or_create_work_pool_queue(
                session=session, work_queue_id=work_queue.id, db=db
            )

        offset += 25
