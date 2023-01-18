"""
Routes for interacting with work queue objects.
"""
from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.schemas import DateTimeTZ
from prefect.orion.utilities.server import OrionRouter
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_WORKERS


def error_404_if_workers_not_enabled():
    if not PREFECT_EXPERIMENTAL_ENABLE_WORKERS:
        raise HTTPException(status_code=404, detail="Workers are not enabled")


router = OrionRouter(
    prefix="/experimental/work_pools",
    tags=["Worker Pools"],
    dependencies=[Depends(error_404_if_workers_not_enabled)],
)


# -----------------------------------------------------
# --
# --
# -- Utility functions & dependencies
# --
# --
# -----------------------------------------------------


class WorkerLookups:
    async def _get_work_pool_id_from_name(
        self, session: AsyncSession, work_pool_name: str
    ) -> UUID:
        """
        Given a work pool name, return its ID. Used for translating
        user-facing APIs (which are name-based) to internal ones (which are
        id-based).
        """
        work_pool = await models.workers.read_work_pool_by_name(
            session=session,
            work_pool_name=work_pool_name,
        )
        if not work_pool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Work pool "{work_pool_name}" not found.',
            )

        return work_pool.id

    async def _get_default_work_pool_queue_id_from_work_pool_name(
        self, session: AsyncSession, work_pool_name: str
    ):
        """
        Given a work pool name, return the ID of its default queue.
        Used for translating user-facing APIs (which are name-based)
        to internal ones (which are id-based).
        """
        work_pool = await models.workers.read_work_pool_by_name(
            session=session,
            work_pool_name=work_pool_name,
        )
        if not work_pool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Work pool "{work_pool_name}" not found.',
            )

        return work_pool.default_queue_id

    async def _get_work_pool_queue_id_from_name(
        self,
        session: AsyncSession,
        work_pool_name: str,
        work_pool_queue_name: str,
        create_queue_if_not_found: bool = False,
    ) -> UUID:
        """
        Given a work pool name and work pool queue name, return the ID of the
        queue. Used for translating user-facing APIs (which are name-based) to
        internal ones (which are id-based).
        """
        work_pool_queue = await models.workers.read_work_pool_queue_by_name(
            session=session,
            work_pool_name=work_pool_name,
            work_pool_queue_name=work_pool_queue_name,
        )
        if not work_pool_queue:
            if not create_queue_if_not_found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Work pool queue '{work_pool_name}/{work_pool_queue_name}' not found.",
                )
            work_pool_id = await self._get_work_pool_id_from_name(
                session=session, work_pool_name=work_pool_name
            )
            work_pool_queue = await models.workers.create_work_pool_queue(
                session=session,
                work_pool_id=work_pool_id,
                work_pool_queue=schemas.actions.WorkPoolQueueCreate(
                    name=work_pool_queue_name
                ),
            )

        return work_pool_queue.id


# -----------------------------------------------------
# --
# --
# -- Worker Pools
# --
# --
# -----------------------------------------------------


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_work_pool(
    work_pool: schemas.actions.WorkPoolCreate,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkPool:
    """
    Creates a new work pool. If a work pool with the same
    name already exists, an error will be raised.
    """

    if work_pool.name.lower().startswith("prefect"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker pools starting with 'Prefect' are reserved for internal use.",
        )

    try:
        async with db.session_context(begin_transaction=True) as session:
            model = await models.workers.create_work_pool(
                session=session, work_pool=work_pool, db=db
            )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A worker with this name already exists.",
        )

    return model


@router.get("/{name}")
async def read_work_pool(
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkPool:
    """
    Read a worker by name
    """

    async with db.session_context() as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )
        return await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool_id, db=db
        )


@router.post("/filter")
async def read_work_pools(
    work_pools: schemas.filters.WorkPoolFilter = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.WorkPool]:
    """
    Read multiple workers
    """
    async with db.session_context() as session:
        return await models.workers.read_work_pools(
            db=db,
            session=session,
            work_pool_filter=work_pools,
            offset=offset,
            limit=limit,
        )


@router.patch("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def update_work_pool(
    work_pool: schemas.actions.WorkPoolUpdate,
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Update a work pool
    """

    # Reserved pools can only updated pause / concurrency
    update_values = work_pool.dict(exclude_unset=True)
    if work_pool_name.lower().startswith("prefect") and (
        set(update_values).difference({"is_paused", "concurrency_limit"})
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker pools starting with 'Prefect' are reserved for internal use "
            "and can only be updated to set concurrency limits or pause.",
        )

    async with db.session_context(begin_transaction=True) as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )
        await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pool_id,
            work_pool=work_pool,
            db=db,
        )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_pool(
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a work pool
    """

    if work_pool_name.lower().startswith("prefect"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker pools starting with 'Prefect' are reserved for internal use and can not be deleted.",
        )

    async with db.session_context(begin_transaction=True) as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )

        await models.workers.delete_work_pool(
            session=session, work_pool_id=work_pool_id, db=db
        )


@router.post("/{name}/get_scheduled_flow_runs")
async def get_scheduled_flow_runs(
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    work_pool_queue_names: List[str] = Body(
        None, description="The names of work pool queues"
    ),
    scheduled_before: DateTimeTZ = Body(
        None, description="The maximum time to look for scheduled flow runs"
    ),
    scheduled_after: DateTimeTZ = Body(
        None, description="The minimum time to look for scheduled flow runs"
    ),
    limit: int = dependencies.LimitBody(),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.WorkerFlowRunResponse]:
    """
    Load scheduled runs for a worker
    """
    async with db.session_context(begin_transaction=True) as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )

        if work_pool_queue_names is None:
            work_pool_queue_ids = None
        else:
            work_pool_queue_ids = []
            for qn in work_pool_queue_names:
                work_pool_queue_ids.append(
                    await worker_lookups._get_work_pool_queue_id_from_name(
                        session=session,
                        work_pool_name=work_pool_name,
                        work_pool_queue_name=qn,
                    )
                )

        queue_response = await models.workers.get_scheduled_flow_runs(
            session=session,
            db=db,
            work_pool_ids=[work_pool_id],
            work_pool_queue_ids=work_pool_queue_ids,
            scheduled_before=scheduled_before,
            scheduled_after=scheduled_after,
            limit=limit,
        )

        return queue_response


# -----------------------------------------------------
# --
# --
# -- Worker Queues
# --
# --
# -----------------------------------------------------


@router.post("/{work_pool_name}/queues", status_code=status.HTTP_201_CREATED)
async def create_work_pool_queue(
    work_pool_queue: schemas.actions.WorkPoolQueueCreate,
    work_pool_name: str = Path(..., description="The work pool name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkPoolQueue:
    """
    Creates a new work pool queue. If a work pool queue with the same
    name already exists, an error will be raised.
    """

    try:
        async with db.session_context(begin_transaction=True) as session:
            work_pool_id = await worker_lookups._get_work_pool_id_from_name(
                session=session,
                work_pool_name=work_pool_name,
            )

            model = await models.workers.create_work_pool_queue(
                session=session,
                work_pool_id=work_pool_id,
                work_pool_queue=work_pool_queue,
                db=db,
            )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A worker with this name already exists.",
        )

    return model


@router.get("/{work_pool_name}/queues/{name}")
async def read_work_pool_queue(
    work_pool_name: str = Path(..., description="The work pool name"),
    work_pool_queue_name: str = Path(
        ..., description="The work pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkPoolQueue:
    """
    Read a work pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        work_pool_queue_id = await worker_lookups._get_work_pool_queue_id_from_name(
            session=session,
            work_pool_name=work_pool_name,
            work_pool_queue_name=work_pool_queue_name,
        )

        return await models.workers.read_work_pool_queue(
            session=session, work_pool_queue_id=work_pool_queue_id, db=db
        )


@router.get("/{work_pool_name}/queues")
async def read_work_pool_queues(
    work_pool_name: str = Path(..., description="The work pool name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.WorkPoolQueue]:
    """
    Read all work pool queues
    """
    async with db.session_context() as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session,
            work_pool_name=work_pool_name,
        )
        return await models.workers.read_work_pool_queues(
            session=session, work_pool_id=work_pool_id, db=db
        )


@router.patch("/{work_pool_name}/queues/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def update_work_pool_queue(
    work_pool_queue: schemas.actions.WorkPoolQueueUpdate,
    work_pool_name: str = Path(..., description="The work pool name"),
    work_pool_queue_name: str = Path(
        ..., description="The work pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Update a work pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        work_pool_queue_id = await worker_lookups._get_work_pool_queue_id_from_name(
            work_pool_name=work_pool_name,
            work_pool_queue_name=work_pool_queue_name,
            session=session,
        )

        await models.workers.update_work_pool_queue(
            session=session,
            work_pool_queue_id=work_pool_queue_id,
            work_pool_queue=work_pool_queue,
            db=db,
        )


@router.delete(
    "/{work_pool_name}/queues/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_work_pool_queue(
    work_pool_name: str = Path(..., description="The work pool name"),
    work_pool_queue_name: str = Path(
        ..., description="The work pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a work pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        work_pool_queue_id = await worker_lookups._get_work_pool_queue_id_from_name(
            session=session,
            work_pool_name=work_pool_name,
            work_pool_queue_name=work_pool_queue_name,
        )

        await models.workers.delete_work_pool_queue(
            session=session, work_pool_queue_id=work_pool_queue_id, db=db
        )


# -----------------------------------------------------
# --
# --
# -- Workers
# --
# --
# -----------------------------------------------------


@router.post(
    "/{work_pool_name}/workers/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def worker_heartbeat(
    work_pool_name: str = Path(..., description="The work pool name"),
    name: str = Body(..., description="The worker process name", embed=True),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )

        await models.workers.worker_heartbeat(
            session=session,
            work_pool_id=work_pool_id,
            worker_name=name,
            db=db,
        )


@router.post("/{work_pool_name}/workers/filter")
async def read_workers(
    work_pool_name: str = Path(..., description="The work pool name"),
    workers: schemas.filters.WorkerFilter = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.Worker]:
    """
    Read all worker processes
    """
    async with db.session_context() as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )
        return await models.workers.read_workers(
            session=session,
            work_pool_id=work_pool_id,
            worker_filter=workers,
            limit=limit,
            offset=offset,
            db=db,
        )
