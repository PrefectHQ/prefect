"""
Routes for interacting with work queue objects.
"""

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import (
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
) -> schemas.responses.WorkPoolResponse:
    """
    Creates a new work pool. If a work pool with the same
    name already exists, an error will be raised.

    For more information, see https://docs.prefect.io/v3/concepts/work-pools.
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

            ret = schemas.responses.WorkPoolResponse.model_validate(
                model, from_attributes=True
            )
            if ret.concurrency_limit is not None:
                ret.active_slots = 0
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
) -> schemas.responses.WorkPoolResponse:
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
        work_pool = schemas.responses.WorkPoolResponse.model_validate(
            orm_work_pool, from_attributes=True
        )

        if work_pool.concurrency_limit is not None:
            work_pool.active_slots = await models.workers.count_work_pool_active_slots(
                session=session, work_pool_id=work_pool_id
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
) -> List[schemas.responses.WorkPoolResponse]:
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
            schemas.responses.WorkPoolResponse.model_validate(w, from_attributes=True)
            for w in orm_work_pools
        ]
        pools_with_limit = [wp for wp in ret if wp.concurrency_limit is not None]
        if pools_with_limit:
            slot_counts = await models.workers.count_work_pool_active_slots_bulk(
                session=session,
                work_pool_ids=[wp.id for wp in pools_with_limit],
            )
            for work_pool in pools_with_limit:
                work_pool.active_slots = slot_counts.get(work_pool.id, 0)
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


@router.post("/{name}/concurrency_status")
async def read_work_pool_concurrency_status(
    work_pool_name: str = Path(..., description="The work pool name", alias="name"),
    page: int = Body(1, ge=1),
    limit: int = dependencies.LimitBody(),
    flow_run_limit: int = Body(10, ge=0, le=200, description="Max flow runs per queue"),
    worker_lookups: WorkerLookups = Depends(WorkerLookups),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.responses.WorkPoolConcurrencyStatus:
    """
    Read concurrency status for a work pool, including per-queue breakdown
    with flow run summaries. Queues are paginated; flow runs per queue are
    capped by flow_run_limit.
    """
    import asyncio

    from prefect.types._datetime import now as prefect_now

    queue_offset = (page - 1) * limit

    async with db.session_context() as session:
        work_pool = await models.workers.read_work_pool_by_name(
            session=session, work_pool_name=work_pool_name
        )
        if not work_pool:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work pool {work_pool_name!r} not found.",
            )

        # Paginate queues in the DB and get total count + active slots
        # concurrently
        (
            work_queues_page,
            total_queue_count,
            total_active,
            counts_by_queue,
        ) = await asyncio.gather(
            models.workers.read_work_queues(
                session=session,
                work_pool_id=work_pool.id,
                offset=queue_offset,
                limit=limit,
            ),
            models.workers.count_work_queues(
                session=session,
                work_pool_id=work_pool.id,
            ),
            models.workers.count_work_pool_slot_holders(
                session=session,
                work_pool_id=work_pool.id,
            ),
            models.workers.count_work_pool_slot_holders_by_queue(
                session=session,
                work_pool_id=work_pool.id,
            ),
        )

        # Only fetch flow run details for the queues on this page
        page_queue_ids = [wq.id for wq in work_queues_page]
        slot_holders = await models.workers.get_work_pool_slot_holders(
            session=session,
            work_pool_id=work_pool.id,
            work_queue_ids=page_queue_ids,
            flow_run_limit=flow_run_limit,
        )

    current_time = prefect_now("UTC")

    # Group flow runs by work queue id
    runs_by_queue: dict[UUID, list[tuple]] = {}
    for run, slot_acquired_at in slot_holders:
        queue_id = run.work_queue_id
        if queue_id is not None:
            runs_by_queue.setdefault(queue_id, []).append((run, slot_acquired_at))

    def _build_summary(run, slot_acquired_at) -> schemas.responses.FlowRunSlotSummary:
        return schemas.responses.FlowRunSlotSummary(
            id=run.id,
            name=run.name,
            state_type=run.state_type.value if run.state_type else "",
            state_name=run.state_name or "",
            start_time=run.start_time,
            duration_in_slot=(
                (current_time - slot_acquired_at).total_seconds()
                if slot_acquired_at
                else None
            ),
        )

    queue_details = []
    for wq in work_queues_page:
        display_tuples = runs_by_queue.get(wq.id, [])
        active = counts_by_queue.get(wq.id, 0)
        queue_details.append(
            schemas.responses.WorkQueueConcurrencyStatusDetail(
                queue_id=wq.id,
                queue_name=wq.name,
                active_slots=active,
                concurrency_limit=wq.concurrency_limit,
                flow_runs=[_build_summary(r, sa) for r, sa in display_tuples],
                flow_run_count=active,
            )
        )

    return schemas.responses.WorkPoolConcurrencyStatus(
        active_slots=total_active,
        concurrency_limit=work_pool.concurrency_limit,
        queues=queue_details,
        count=total_queue_count,
        limit=limit,
        pages=(total_queue_count + limit - 1) // limit if limit > 0 else 0,
        page=page,
    )


@router.post("/{name}/get_scheduled_flow_runs")
async def get_scheduled_flow_runs(
    docket: dependencies.Docket,
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

    await docket.add(
        mark_work_queues_ready,
        key=f"mark_work_queues_ready:work_pool:{work_pool_id}",
    )(
        polled_work_queue_ids=[
            wq.id for wq in work_queues if wq.status != WorkQueueStatus.NOT_READY
        ],
        ready_work_queue_ids=[
            wq.id for wq in work_queues if wq.status == WorkQueueStatus.NOT_READY
        ],
    )

    await docket.add(
        mark_deployments_ready,
        key=f"mark_deployments_ready:work_pool:{work_pool_id}",
    )(
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

    For more information, see https://docs.prefect.io/v3/concepts/work-pools#work-queues.
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

            response = schemas.responses.WorkQueueResponse.model_validate(
                model, from_attributes=True
            )
            if response.concurrency_limit is not None:
                response.active_slots = 0
    except sa.exc.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A work queue with this name already exists in work pool"
                " {work_pool_name!r}."
            ),
        )

    return response


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

        response = schemas.responses.WorkQueueResponse.model_validate(
            model, from_attributes=True
        )

        if response.concurrency_limit is not None:
            response.active_slots = await models.workers.count_work_queue_active_slots(
                session=session, work_queue_id=work_queue_id
            )

    return response


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

        ret = [
            schemas.responses.WorkQueueResponse.model_validate(wq, from_attributes=True)
            for wq in wqs
        ]
        queues_with_limit = [wq for wq in ret if wq.concurrency_limit is not None]
        if queues_with_limit:
            slot_counts = await models.workers.count_work_queue_active_slots_bulk(
                session=session,
                work_queue_ids=[wq.id for wq in queues_with_limit],
            )
            for wq_response in queues_with_limit:
                wq_response.active_slots = slot_counts.get(wq_response.id, 0)

    return ret


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
