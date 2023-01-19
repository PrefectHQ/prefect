"""
Functions to assist with migrating from work queues to worker pools
"""
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.orion import models, schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.utilities.schemas import DateTimeTZ

AGENT_WORKER_POOL_NAME = "Prefect Agents"


@inject_db
async def get_or_create_worker_pool(session: AsyncSession, db: OrionDBInterface = None):
    """
    Gets or creates the Prefect Agents worker pool.

    Args:
        session (AsyncSession): a database session

    Returns:
        db.WorkerPool: the WorkerPool

    """
    pool = await models.workers.read_worker_pool_by_name(
        session=session, worker_pool_name=AGENT_WORKER_POOL_NAME
    )
    if pool is None:
        pool = await models.workers.create_worker_pool(
            session=session,
            worker_pool=schemas.actions.WorkerPoolCreate(
                name="Prefect Agents",
                description="A worker pool for Prefect Agents",
                type="AGENT",
            ),
        )
    return pool


@inject_db
async def get_or_create_worker_pool_queue(
    session: AsyncSession,
    work_queue_id: UUID = None,
    work_queue_name: str = None,
    db: OrionDBInterface = None,
):

    """
    Args:
        session (AsyncSession): a database session
        work_queue_id (UUID): the work queue id
        work_queue_name (str): the work queue name
        db (OrionDBInterface, optional): a database interface. Defaults to None.
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

    # get or create the agents pool
    pool = await get_or_create_worker_pool(session=session, db=db)

    # get or create the worker pool queue
    worker_pool_queue = await models.workers.read_worker_pool_queue_by_name(
        session=session,
        worker_pool_name=AGENT_WORKER_POOL_NAME,
        worker_pool_queue_name=work_queue.name,
    )
    if worker_pool_queue is None:
        worker_pool_queue = await models.workers.create_worker_pool_queue(
            session=session,
            worker_pool_id=pool.id,
            worker_pool_queue=schemas.actions.WorkerPoolQueueCreate(
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
                db.Deployment.worker_pool_queue_id.is_(None),
            )
            .values(worker_pool_queue_id=worker_pool_queue.id)
        )
        await session.execute(update_deployments_stmt)

        # update scheduled flow runs to point at the new work queue
        update_flow_runs_stmt = (
            sa.update(db.FlowRun)
            .where(
                db.FlowRun.work_queue_name == work_queue.name,
                db.FlowRun.state_type == "SCHEDULED",
                db.FlowRun.worker_pool_queue_id.is_(None),
            )
            .values(worker_pool_queue_id=worker_pool_queue.id)
        )
        await session.execute(update_flow_runs_stmt)

    # return the new queue
    return worker_pool_queue


@inject_db
async def get_runs_from_worker_pool_queue(
    session: AsyncSession,
    work_queue_id: UUID,
    scheduled_before: DateTimeTZ = None,
    limit: int = None,
    db: OrionDBInterface = None,
):
    worker_pool_queue = await get_or_create_worker_pool_queue(
        session=session, work_queue_id=work_queue_id, db=db
    )

    return await models.workers.get_scheduled_flow_runs(
        session=session,
        worker_pool_ids=[worker_pool_queue.worker_pool_id],
        worker_pool_queue_ids=[worker_pool_queue.id],
        scheduled_before=scheduled_before,
        limit=limit,
        db=db,
    )


@inject_db
async def migrate_all_work_queues(
    session: AsyncSession,
    db: OrionDBInterface = None,
):
    """
    Migrates all existing work queues to the Prefect Agent worker pool.

    Can be run at any time to facilitate user-initiated migrations without
    waiting for an agent to poll.

    Args:
        session (AsyncSession): a database session
        db (OrionDBInterface, optional): a database interface. Defaults to None.
    """
    for work_queue in await models.work_queues.read_work_queues(session=session):
        await get_or_create_worker_pool_queue(
            session=session, work_queue_id=work_queue.id, db=db
        )


@inject_db
async def heartbeat_legacy_agent(db: OrionDBInterface):
    async with db.session_context(begin_transaction=True) as session:
        worker_pool = await get_or_create_worker_pool(session=session, db=db)
        await models.workers.worker_heartbeat(
            session=session,
            worker_pool_id=worker_pool.id,
            worker_name="Legacy Prefect Agent",
        )
