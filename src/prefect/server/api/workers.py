"""
Routes for interacting with work queue objects.
"""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path,
    status,
)
from packaging.version import Version
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect._internal.uuid7 import uuid7
from prefect.server.api.validation import validate_job_variable_defaults_for_work_pool
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models.deployments import mark_deployments_ready
from prefect.server.models.work_queues import (
    emit_work_queue_status_event,
    mark_work_queues_ready,
)
from prefect.server.models.workers import emit_work_pool_status_event
from prefect.server.schemas.statuses import WorkQueueStatus
from prefect.server.utilities.server import PrefectRouter
from prefect.types import DateTime
from prefect.types._datetime import now

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMWorkQueue

router: PrefectRouter = PrefectRouter(
    prefix="/work_pools",
    tags=["Work Pools"],
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

    async def _get_default_work_queue_id_from_work_pool_name(
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

    async def _get_work_queue_from_name(
        self,
        session: AsyncSession,
        work_pool_name: str,
        work_queue_name: str,
        create_queue_if_not_found: bool = False,
    ) -> "ORMWorkQueue":
        """
        Given a work pool name and work pool queue name, return the ID of the
        queue. Used for translating user-facing APIs (which are name-based) to
        internal ones (which are id-based).
        """
        work_queue = await models.workers.read_work_queue_by_name(
            session=session,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
        )
        if not work_queue:
            if not create_queue_if_not_found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"Work pool queue '{work_pool_name}/{work_queue_name}' not"
                        " found."
                    ),
                )
            work_pool_id = await self._get_work_pool_id_from_name(
                session=session, work_pool_name=work_pool_name
            )
            work_queue = await models.workers.create_work_queue(
                session=session,
                work_pool_id=work_pool_id,
                work_queue=schemas.actions.WorkQueueCreate(name=work_queue_name),
            )

        return work_queue

    async def _get_work_queue_id_from_name(
        self,
        session: AsyncSession,
        work_pool_name: str,
        work_queue_name: str,
        create_queue_if_not_found: bool = False,
    ) -> UUID:
        queue = await self._get_work_queue_from_name(
            session=session,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
            create_queue_if_not_found=create_queue_if_not_found,
        )
        return queue.id


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
    db: PrefectDBInterface = Depends(provide_database_interface),
    prefect_client_version: Optional[str] = Depends(
        dependencies.get_prefect_client_version
    ),
) -> schemas.core.WorkPool:
    """
    Creates a new work pool. If a work pool with the same
    name already exists, an error will be raised.

    For more information, see https://docs.prefect.io/v3/deploy/infrastructure-concepts/work-pools.
    """
    if work_pool.name.lower().startswith("prefect"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Work pools starting with 'Prefect' are reserved for internal use.",
        )

    try:
        async with db.session_context(begin_transaction=True) as session:
            await validate_job_variable_defaults_for_work_pool(
                session, work_pool.name, work_pool.base_job_template
            )
            model = await models.workers.create_work_pool(
                session=session, work_pool=work_pool
            )

            await emit_work_pool_status_event(
                event_id=uuid7(),
                occurred=now("UTC"),
                pre_update_work_pool=None,
                work_pool=model,
            )

            ret = schemas.core.WorkPool.model_validate(model, from_attributes=True)
            if prefect_client_version and Version(prefect_client_version) <= Version(
                "3.3.7"
            ):
                # Client versions 3.3.7 and below do not support the default_result_storage_block_id field and will error
                # when receiving it.
                del ret.storage_configuration.default_result_storage_block_id
            return ret

    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A work pool with this name already exists.",
        )


@router.get("/{name}")
async def read_work_pool(
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
    prefect_client_version: Optional[str] = Depends(
        dependencies.get_prefect_client_version
    ),
) -> schemas.core.WorkPool:
    """
    Read a work pool by name
    """

    async with db.session_context() as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )
        orm_work_pool = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool_id
        )
        work_pool = schemas.core.WorkPool.model_validate(
            orm_work_pool, from_attributes=True
        )

        if prefect_client_version and Version(prefect_client_version) <= Version(
            "3.3.7"
        ):
            # Client versions 3.3.7 and below do not support the default_result_storage_block_id field and will error
            # when receiving it.
            del work_pool.storage_configuration.default_result_storage_block_id

        return work_pool


@router.post("/filter")
async def read_work_pools(
    work_pools: Optional[schemas.filters.WorkPoolFilter] = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    db: PrefectDBInterface = Depends(provide_database_interface),
    prefect_client_version: Optional[str] = Depends(
        dependencies.get_prefect_client_version
    ),
) -> List[schemas.core.WorkPool]:
    """
    Read multiple work pools
    """
    async with db.session_context() as session:
        orm_work_pools = await models.workers.read_work_pools(
            session=session,
            work_pool_filter=work_pools,
            offset=offset,
            limit=limit,
        )
        ret = [
            schemas.core.WorkPool.model_validate(w, from_attributes=True)
            for w in orm_work_pools
        ]
        if prefect_client_version and Version(prefect_client_version) <= Version(
            "3.3.7"
        ):
            # Client versions 3.3.7 and below do not support the default_result_storage_block_id field and will error
            # when receiving it.
            for work_pool in ret:
                del work_pool.storage_configuration.default_result_storage_block_id
        return ret


@router.post("/count")
async def count_work_pools(
    work_pools: Optional[schemas.filters.WorkPoolFilter] = Body(None, embed=True),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> int:
    """
    Count work pools
    """
    async with db.session_context() as session:
        return await models.workers.count_work_pools(
            session=session, work_pool_filter=work_pools
        )


@router.patch("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def update_work_pool(
    work_pool: schemas.actions.WorkPoolUpdate,
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Update a work pool
    """

    # Reserved pools can only updated pause / concurrency
    update_values = work_pool.model_dump(exclude_unset=True)
    if work_pool_name.lower().startswith("prefect") and (
        set(update_values).difference({"is_paused", "concurrency_limit"})
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Work pools starting with 'Prefect' are reserved for internal use "
                "and can only be updated to set concurrency limits or pause."
            ),
        )

    async with db.session_context(begin_transaction=True) as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )
        await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pool_id,
            work_pool=work_pool,
            emit_status_change=emit_work_pool_status_event,
        )


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_pool(
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Delete a work pool
    """

    if work_pool_name.lower().startswith("prefect"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Work pools starting with 'Prefect' are reserved for internal use and"
                " can not be deleted."
            ),
        )

    async with db.session_context(begin_transaction=True) as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )

        await models.workers.delete_work_pool(
            session=session, work_pool_id=work_pool_id
        )


@router.post("/{name}/get_scheduled_flow_runs")
async def get_scheduled_flow_runs(
    background_tasks: BackgroundTasks,
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    work_queue_names: List[str] = Body(
        None, description="The names of work pool queues"
    ),
    scheduled_before: DateTime = Body(
        None, description="The maximum time to look for scheduled flow runs"
    ),
    scheduled_after: DateTime = Body(
        None, description="The minimum time to look for scheduled flow runs"
    ),
    limit: int = dependencies.LimitBody(),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.WorkerFlowRunResponse]:
    """
    Load scheduled runs for a worker
    """
    async with db.session_context() as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )

        if not work_queue_names:
            work_queues = list(
                await models.workers.read_work_queues(
                    session=session, work_pool_id=work_pool_id
                )
            )
            # None here instructs get_scheduled_flow_runs to use the default behavior
            # of just operating on all work queues of the pool
            work_queue_ids = None
        else:
            work_queues = [
                await worker_lookups._get_work_queue_from_name(
                    session=session,
                    work_pool_name=work_pool_name,
                    work_queue_name=name,
                )
                for name in work_queue_names
            ]
            work_queue_ids = [wq.id for wq in work_queues]

    async with db.session_context(begin_transaction=True) as session:
        queue_response = await models.workers.get_scheduled_flow_runs(
            session=session,
            work_pool_ids=[work_pool_id],
            work_queue_ids=work_queue_ids,
            scheduled_before=scheduled_before,
            scheduled_after=scheduled_after,
            limit=limit,
        )

    background_tasks.add_task(
        mark_work_queues_ready,
        db=db,
        polled_work_queue_ids=[
            wq.id for wq in work_queues if wq.status != WorkQueueStatus.NOT_READY
        ],
        ready_work_queue_ids=[
            wq.id for wq in work_queues if wq.status == WorkQueueStatus.NOT_READY
        ],
    )

    background_tasks.add_task(
        mark_deployments_ready,
        db=db,
        work_queue_ids=[wq.id for wq in work_queues],
    )

    return queue_response


# -----------------------------------------------------
# --
# --
# -- Work Pool Queues
# --
# --
# -----------------------------------------------------


@router.post("/{work_pool_name}/queues", status_code=status.HTTP_201_CREATED)
async def create_work_queue(
    work_queue: schemas.actions.WorkQueueCreate,
    work_pool_name: str = Path(..., description="The work pool name"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.WorkQueueResponse:
    """
    Creates a new work pool queue. If a work pool queue with the same
    name already exists, an error will be raised.

    For more information, see https://docs.prefect.io/v3/deploy/infrastructure-concepts/work-pools#work-queues.
    """

    try:
        async with db.session_context(begin_transaction=True) as session:
            work_pool_id = await worker_lookups._get_work_pool_id_from_name(
                session=session,
                work_pool_name=work_pool_name,
            )

            model = await models.workers.create_work_queue(
                session=session,
                work_pool_id=work_pool_id,
                work_queue=work_queue,
            )
    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A work queue with this name already exists in work pool"
                " {work_pool_name!r}."
            ),
        )

    return schemas.responses.WorkQueueResponse.model_validate(
        model, from_attributes=True
    )


@router.get("/{work_pool_name}/queues/{name}")
async def read_work_queue(
    work_pool_name: str = Path(..., description="The work pool name"),
    work_queue_name: str = Path(
        ..., description="The work pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.WorkQueueResponse:
    """
    Read a work pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        work_queue_id = await worker_lookups._get_work_queue_id_from_name(
            session=session,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
        )

        model = await models.workers.read_work_queue(
            session=session, work_queue_id=work_queue_id
        )

    return schemas.responses.WorkQueueResponse.model_validate(
        model, from_attributes=True
    )


@router.post("/{work_pool_name}/queues/filter")
async def read_work_queues(
    work_pool_name: str = Path(..., description="The work pool name"),
    work_queues: schemas.filters.WorkQueueFilter = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.WorkQueueResponse]:
    """
    Read all work pool queues
    """
    async with db.session_context() as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session,
            work_pool_name=work_pool_name,
        )
        wqs = await models.workers.read_work_queues(
            session=session,
            work_pool_id=work_pool_id,
            work_queue_filter=work_queues,
            limit=limit,
            offset=offset,
        )

    return [
        schemas.responses.WorkQueueResponse.model_validate(wq, from_attributes=True)
        for wq in wqs
    ]


@router.patch("/{work_pool_name}/queues/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def update_work_queue(
    work_queue: schemas.actions.WorkQueueUpdate,
    work_pool_name: str = Path(..., description="The work pool name"),
    work_queue_name: str = Path(
        ..., description="The work pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Update a work pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        work_queue_id = await worker_lookups._get_work_queue_id_from_name(
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
            session=session,
        )

        await models.workers.update_work_queue(
            session=session,
            work_queue_id=work_queue_id,
            work_queue=work_queue,
            emit_status_change=emit_work_queue_status_event,
        )


@router.delete(
    "/{work_pool_name}/queues/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_work_queue(
    work_pool_name: str = Path(..., description="The work pool name"),
    work_queue_name: str = Path(
        ..., description="The work pool queue name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Delete a work pool queue
    """

    async with db.session_context(begin_transaction=True) as session:
        work_queue_id = await worker_lookups._get_work_queue_id_from_name(
            session=session,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
        )

        await models.workers.delete_work_queue(
            session=session, work_queue_id=work_queue_id
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
    heartbeat_interval_seconds: Optional[int] = Body(
        None, description="The worker's heartbeat interval in seconds", embed=True
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    async with db.session_context(begin_transaction=True) as session:
        work_pool = await models.workers.read_work_pool_by_name(
            session=session,
            work_pool_name=work_pool_name,
        )
        if not work_pool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Work pool "{work_pool_name}" not found.',
            )

        await models.workers.worker_heartbeat(
            session=session,
            work_pool_id=work_pool.id,
            worker_name=name,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )

        if work_pool.status == schemas.statuses.WorkPoolStatus.NOT_READY:
            await models.workers.update_work_pool(
                session=session,
                work_pool_id=work_pool.id,
                work_pool=schemas.internal.InternalWorkPoolUpdate(
                    status=schemas.statuses.WorkPoolStatus.READY
                ),
                emit_status_change=emit_work_pool_status_event,
            )


@router.post("/{work_pool_name}/workers/filter")
async def read_workers(
    work_pool_name: str = Path(..., description="The work pool name"),
    workers: Optional[schemas.filters.WorkerFilter] = None,
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.WorkerResponse]:
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
        )


@router.delete(
    "/{work_pool_name}/workers/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_worker(
    work_pool_name: str = Path(..., description="The work pool name"),
    worker_name: str = Path(
        ..., description="The work pool's worker name", alias="name"
    ),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Delete a work pool's worker
    """

    async with db.session_context(begin_transaction=True) as session:
        work_pool_id = await worker_lookups._get_work_pool_id_from_name(
            session=session, work_pool_name=work_pool_name
        )
        deleted = await models.workers.delete_worker(
            session=session, work_pool_id=work_pool_id, worker_name=worker_name
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found."
            )
