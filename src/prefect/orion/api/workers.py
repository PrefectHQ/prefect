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
    prefix="/experimental/worker_pools",
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
    async def _get_worker_pool_id_from_name(
        self, session: AsyncSession, worker_pool_name: str
    ) -> UUID:
        """
        Given a worker pool name, return its ID. Used for translating
        user-facing APIs (which are name-based) to internal ones (which are
        id-based).
        """
        worker_pool = await models.workers.read_worker_pool_by_name(
            session=session,
            worker_pool_name=worker_pool_name,
        )
        if not worker_pool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Worker pool "{worker_pool_name}" not found.',
            )

        return worker_pool.id

    async def _get_worker_pool_queue_id_from_name(
        self, session: AsyncSession, worker_pool_name: str, worker_pool_queue_name: str
    ) -> UUID:
        """
        Given a worker pool name and worker pool queue name, return the ID of the
        queue. Used for translating user-facing APIs (which are name-based) to
        internal ones (which are id-based).
        """
        worker_pool_queue = await models.workers.read_worker_pool_queue_by_name(
            session=session,
            worker_pool_name=worker_pool_name,
            worker_pool_queue_name=worker_pool_queue_name,
        )
        if not worker_pool_queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Worker queue '{worker_pool_name}/{worker_pool_queue_name}' not found.",
            )

        return worker_pool_queue.id


# -----------------------------------------------------
# --
# --
# -- Worker Pools
# --
# --
# -----------------------------------------------------


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_worker_pool(
    worker_pool: schemas.actions.WorkerPoolCreate,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkerPool:
    """
    Creates a new worker pool. If a worker pool with the same
    name already exists, an error will be raised.
    """

    if worker_pool.name.lower().startswith("prefect"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker pools starting with 'Prefect' are reserved for internal use.",
        )

    try:
        async with db.session_context(begin_transaction=True) as session:
            model = await models.workers.create_worker_pool(
                session=session, worker_pool=worker_pool, db=db
            )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A worker with this name already exists.",
        )

    return model


@router.get("/{name}")
async def read_worker_pool(
    worker_pool_name: str = Path(..., description="The worker pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkerPool:
    """
    Read a worker by name
    """

    async with db.session_context() as session:
        worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
            session=session, worker_pool_name=worker_pool_name
        )
        return await models.workers.read_worker_pool(
            session=session, worker_pool_id=worker_pool_id, db=db
        )


@router.post("/filter")
async def read_worker_pools(
    worker_pools: schemas.filters.WorkerPoolFilter = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.WorkerPool]:
    """
    Read multiple workers
    """
    async with db.session_context() as session:
        return await models.workers.read_worker_pools(
            db=db,
            session=session,
            worker_pool_filter=worker_pools,
            offset=offset,
            limit=limit,
        )


@router.patch("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def update_worker_pool(
    worker_pool: schemas.actions.WorkerPoolUpdate,
    worker_pool_name: str = Path(..., description="The worker pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Update a worker pool
    """

    # Reserved pools can only updated pause / concurrency
    update_values = worker_pool.dict(exclude_unset=True)
    if worker_pool_name.lower().startswith("prefect") and (
        set(update_values).difference({"is_paused", "concurrency_limit"})
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker pools starting with 'Prefect' are reserved for internal use "
            "and can only be updated to set concurrency limits or pause.",
        )

    async with db.session_context(begin_transaction=True) as session:
        worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
            session=session, worker_pool_name=worker_pool_name
        )
        await models.workers.update_worker_pool(
            session=session,
            worker_pool_id=worker_pool_id,
            worker_pool=worker_pool,
            db=db,
        )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_worker_pool(
    worker_pool_name: str = Path(..., description="The worker pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a worker pool
    """

    if worker_pool_name.lower().startswith("prefect"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker pools starting with 'Prefect' are reserved for internal use and can not be deleted.",
        )

    async with db.session_context(begin_transaction=True) as session:
        worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
            session=session, worker_pool_name=worker_pool_name
        )

        await models.workers.delete_worker_pool(
            session=session, worker_pool_id=worker_pool_id, db=db
        )


@router.post("/{name}/get_scheduled_flow_runs")
async def get_scheduled_flow_runs(
    worker_pool_name: str = Path(..., description="The worker pool name", alias="name"),
    worker_pool_queue_names: List[str] = Body(
        None, description="The names of worker pool queues"
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
        worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
            session=session, worker_pool_name=worker_pool_name
        )

        if worker_pool_queue_names is None:
            worker_pool_queue_ids = None
        else:
            worker_pool_queue_ids = []
            for qn in worker_pool_queue_names:
                worker_pool_queue_ids.append(
                    await worker_lookups._get_worker_pool_queue_id_from_name(
                        session=session,
                        worker_pool_name=worker_pool_name,
                        worker_pool_queue_name=qn,
                    )
                )

        queue_response = await models.workers.get_scheduled_flow_runs(
            session=session,
            db=db,
            worker_pool_ids=[worker_pool_id],
            worker_pool_queue_ids=worker_pool_queue_ids,
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


@router.post("/{worker_pool_name}/queues", status_code=status.HTTP_201_CREATED)
async def create_worker_pool_queue(
    worker_pool_queue: schemas.actions.WorkerPoolQueueCreate,
    worker_pool_name: str = Path(..., description="The worker pool name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkerPoolQueue:
    """
    Creates a new worker pool queue. If a worker pool queue with the same
    name already exists, an error will be raised.
    """

    try:
        async with db.session_context(begin_transaction=True) as session:
            worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
                session=session,
                worker_pool_name=worker_pool_name,
            )

            model = await models.workers.create_worker_pool_queue(
                session=session,
                worker_pool_id=worker_pool_id,
                worker_pool_queue=worker_pool_queue,
                db=db,
            )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A worker with this name already exists.",
        )

    return model


@router.get("/{worker_pool_name}/queues/{name}")
async def read_worker_pool_queue(
    worker_pool_name: str = Path(..., description="The worker pool name"),
    worker_pool_queue_name: str = Path(
        ..., description="The worker pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.WorkerPoolQueue:
    """
    Read a worker pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        worker_pool_queue_id = await worker_lookups._get_worker_pool_queue_id_from_name(
            session=session,
            worker_pool_name=worker_pool_name,
            worker_pool_queue_name=worker_pool_queue_name,
        )

        return await models.workers.create_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue_id, db=db
        )


@router.get("/{worker_pool_name}/queues")
async def read_worker_pool_queues(
    worker_pool_name: str = Path(..., description="The worker pool name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.WorkerPoolQueue]:
    """
    Read all worker pool queues
    """
    async with db.session_context() as session:
        worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
            session=session,
            worker_pool_name=worker_pool_name,
        )
        return await models.workers.read_worker_pool_queues(
            session=session, worker_pool_id=worker_pool_id, db=db
        )


@router.patch(
    "/{worker_pool_name}/queues/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def update_worker_pool_queue(
    worker_pool_queue: schemas.actions.WorkerPoolQueueUpdate,
    worker_pool_name: str = Path(..., description="The worker pool name"),
    worker_pool_queue_name: str = Path(
        ..., description="The worker pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Update a worker pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        worker_pool_queue_id = await worker_lookups._get_worker_pool_queue_id_from_name(
            worker_pool_name=worker_pool_name,
            worker_pool_queue_name=worker_pool_queue_name,
            session=session,
            db=db,
        )

        await models.workers.update_worker_pool_queue(
            session=session,
            worker_pool_queue_id=worker_pool_queue_id,
            worker_pool_queue=worker_pool_queue,
            db=db,
        )


@router.delete(
    "/{worker_pool_name}/queues/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_worker_pool_queue(
    worker_pool_name: str = Path(..., description="The worker pool name"),
    worker_pool_queue_name: str = Path(
        ..., description="The worker pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a worker pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        worker_pool_queue_id = await worker_lookups._get_worker_pool_queue_id_from_name(
            session=session,
            worker_pool_name=worker_pool_name,
            worker_pool_queue_name=worker_pool_queue_name,
        )

        await models.workers.delete_worker_pool_queue(
            session=session, worker_pool_queue_id=worker_pool_queue_id, db=db
        )


# -----------------------------------------------------
# --
# --
# -- Workers
# --
# --
# -----------------------------------------------------


@router.post(
    "/{worker_pool_name}/workers/heartbeat",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def worker_heartbeat(
    worker_pool_name: str = Path(..., description="The worker pool name"),
    name: str = Body(..., description="The worker process name", embed=True),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
            session=session, worker_pool_name=worker_pool_name
        )

        await models.workers.worker_heartbeat(
            session=session,
            worker_pool_id=worker_pool_id,
            worker_name=name,
            db=db,
        )


@router.post("/{worker_pool_name}/workers/filter")
async def read_workers(
    worker_pool_name: str = Path(..., description="The worker pool name"),
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
        worker_pool_id = await worker_lookups._get_worker_pool_id_from_name(
            session=session, worker_pool_name=worker_pool_name
        )
        return await models.workers.read_workers(
            session=session,
            worker_pool_id=worker_pool_id,
            worker_filter=workers,
            limit=limit,
            offset=offset,
            db=db,
        )
