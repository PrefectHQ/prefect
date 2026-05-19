"""
Routes for interacting with work queue objects.
"""

from logging import Logger
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import (
    Body,
    Depends,
    HTTPException,
    Path,
    WebSocket,
    status,
)
from packaging.version import Version
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.worker_channel import (
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORKER_CHANNEL_CLOSE_POLICIES,
    WORKER_HEARTBEAT_CAPABILITY,
    WorkerChannelCloseReason,
    WorkerChannelProtocolError,
    WorkerHeartbeatFrame,
    WorkerHelloFrame,
    WorkerReadyFrame,
    WorkPoolSnapshot,
    WorkPoolSnapshotPayload,
    select_worker_channel_version,
    validate_worker_channel_frame,
)
from prefect.logging import get_logger
from prefect.server.api.validation import validate_job_variable_defaults_for_work_pool
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models.deployments import mark_deployments_ready
from prefect.server.models.work_queues import (
    emit_work_queue_status_event,
    mark_work_queues_ready,
)
from prefect.server.models.workers import emit_work_pool_status_event
from prefect.server.schemas.statuses import WorkQueueStatus
from prefect.server.utilities import subscriptions
from prefect.server.utilities.server import PrefectRouter
from prefect.types import DateTime
from prefect.types._datetime import now

if TYPE_CHECKING:
    from prefect.server.database.orm_models import WorkPool as ORMWorkPool
    from prefect.server.database.orm_models import WorkQueue as ORMWorkQueue

router: PrefectRouter = PrefectRouter(
    prefix="/work_pools",
    tags=["Work Pools"],
)
logger: Logger = get_logger("prefect.server.api.workers")

_OSS_WORKER_CHANNEL_ACCEPTED_CAPABILITIES = [
    WORKER_HEARTBEAT_CAPABILITY,
    WORK_POOL_SNAPSHOT_CAPABILITY,
]


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


class WorkerChannelSetupError(Exception):
    def __init__(self, close_reason: WorkerChannelCloseReason, detail: str):
        super().__init__(detail)
        self.close_reason = close_reason
        self.detail = detail


async def _close_worker_channel(
    websocket: WebSocket, close_reason: WorkerChannelCloseReason
) -> None:
    policy = WORKER_CHANNEL_CLOSE_POLICIES[close_reason]
    await websocket.close(code=policy.websocket_code, reason=close_reason.value)


async def _receive_worker_hello(websocket: WebSocket) -> WorkerHelloFrame:
    try:
        message = await websocket.receive_json()
        frame = validate_worker_channel_frame(message)
    except ValidationError as exc:
        raise WorkerChannelSetupError(
            WorkerChannelCloseReason.PROTOCOL_ERROR,
            "Worker channel received a malformed hello frame",
        ) from exc
    except ValueError as exc:
        raise WorkerChannelSetupError(
            WorkerChannelCloseReason.PROTOCOL_ERROR,
            "Worker channel received invalid JSON during setup",
        ) from exc

    if not isinstance(frame, WorkerHelloFrame):
        raise WorkerChannelSetupError(
            WorkerChannelCloseReason.PROTOCOL_ERROR,
            "Expected worker.hello.v1 during worker channel setup",
        )

    return frame


async def _resolve_worker_channel_work_pool(
    session: AsyncSession,
    work_pool_name: str,
    hello: WorkerHelloFrame,
) -> "ORMWorkPool":
    work_pool = await models.workers.read_work_pool_by_name(
        session=session,
        work_pool_name=work_pool_name,
    )

    default_base_job_template = hello.payload.default_base_job_template
    if work_pool is None:
        if not hello.payload.create_pool_if_not_found:
            raise WorkerChannelSetupError(
                WorkerChannelCloseReason.AUTHORIZATION_FAILED,
                "work_pool_not_found",
            )

        if work_pool_name.lower().startswith("prefect"):
            raise WorkerChannelSetupError(
                WorkerChannelCloseReason.AUTHORIZATION_FAILED,
                "work_pool_creation_unauthorized",
            )

        await validate_job_variable_defaults_for_work_pool(
            session, work_pool_name, default_base_job_template
        )
        try:
            async with session.begin_nested():
                work_pool = await models.workers.create_work_pool(
                    session=session,
                    work_pool=schemas.actions.WorkPoolCreate(
                        name=work_pool_name,
                        type=hello.payload.worker_type,
                        base_job_template=default_base_job_template,
                    ),
                )
        except sa.exc.IntegrityError:
            work_pool = await models.workers.read_work_pool_by_name(
                session=session,
                work_pool_name=work_pool_name,
            )
            if work_pool is None:
                raise
        return work_pool

    return work_pool


async def _resolve_worker_channel_work_queues(
    session: AsyncSession,
    work_pool_id: UUID,
    work_pool_name: str,
    work_queue_names: list[str],
) -> list["ORMWorkQueue"]:
    if not work_queue_names:
        return list(
            await models.workers.read_work_queues(
                session=session, work_pool_id=work_pool_id
            )
        )

    work_queues = []
    for work_queue_name in dict.fromkeys(work_queue_names):
        work_queue = await models.workers.read_work_queue_by_name(
            session=session,
            work_pool_name=work_pool_name,
            work_queue_name=work_queue_name,
        )
        if work_queue is None:
            raise WorkerChannelSetupError(
                WorkerChannelCloseReason.AUTHORIZATION_FAILED,
                "work_queue_not_found",
            )
        work_queues.append(work_queue)

    return work_queues


async def _build_worker_channel_work_pool_snapshot(
    session: AsyncSession,
    work_pool: "ORMWorkPool",
) -> WorkPoolSnapshot:
    work_pool_response = schemas.responses.WorkPoolResponse.model_validate(
        work_pool, from_attributes=True
    )

    if work_pool_response.concurrency_limit is not None:
        work_pool_response.active_slots = (
            await models.workers.count_work_pool_active_slots(
                session=session,
                work_pool_id=work_pool.id,
            )
        )

    return WorkPoolSnapshot.model_validate(work_pool_response.model_dump(mode="json"))


async def _build_worker_ready_frame(
    session: AsyncSession,
    work_pool_name: str,
    hello: WorkerHelloFrame,
) -> WorkerReadyFrame:
    try:
        selected_channel_version = select_worker_channel_version(
            hello.payload.supported_channel_versions
        )
    except WorkerChannelProtocolError as exc:
        raise WorkerChannelSetupError(exc.close_reason, str(exc)) from exc

    work_pool = await _resolve_worker_channel_work_pool(
        session=session,
        work_pool_name=work_pool_name,
        hello=hello,
    )
    work_queues = await _resolve_worker_channel_work_queues(
        session=session,
        work_pool_id=work_pool.id,
        work_pool_name=work_pool_name,
        work_queue_names=hello.payload.work_queue_names,
    )
    default_base_job_template = hello.payload.default_base_job_template
    if not work_pool.base_job_template and default_base_job_template:
        await validate_job_variable_defaults_for_work_pool(
            session, work_pool_name, default_base_job_template
        )
        await models.workers.update_work_pool(
            session=session,
            work_pool_id=work_pool.id,
            work_pool=schemas.actions.WorkPoolUpdate(
                base_job_template=default_base_job_template
            ),
            emit_status_change=emit_work_pool_status_event,
        )
        refreshed = await models.workers.read_work_pool(
            session=session, work_pool_id=work_pool.id
        )
        assert refreshed is not None
        work_pool = refreshed

    try:
        worker = await models.workers.record_worker_heartbeat(
            session=session,
            work_pool=work_pool,
            worker_name=hello.payload.worker_name,
            heartbeat_interval_seconds=hello.payload.heartbeat_interval_seconds,
            emit_status_change=emit_work_pool_status_event,
        )
    except Exception as exc:
        raise WorkerChannelSetupError(
            WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED,
            "worker_channel_initial_heartbeat_failed",
        ) from exc

    refreshed_work_pool = await models.workers.read_work_pool(
        session=session, work_pool_id=work_pool.id
    )
    assert refreshed_work_pool is not None
    initial_snapshot = WorkPoolSnapshotPayload(
        snapshot_sequence=1,
        reason="initial",
        work_pool=await _build_worker_channel_work_pool_snapshot(
            session=session,
            work_pool=refreshed_work_pool,
        ),
    )

    requested_capabilities = list(dict.fromkeys(hello.payload.requested_capabilities))
    accepted = _OSS_WORKER_CHANNEL_ACCEPTED_CAPABILITIES
    rejected = [
        capability
        for capability in requested_capabilities
        if capability not in set(accepted)
    ]

    return WorkerReadyFrame(
        type="worker.ready.v1",
        id=uuid7(),
        sent_at=now("UTC"),
        payload={
            "consumer_id": hello.payload.consumer_id,
            "worker_id": worker.id,
            "selected_channel_version": selected_channel_version,
            "effective_heartbeat_interval_seconds": (
                hello.payload.heartbeat_interval_seconds
            ),
            "accepted_capabilities": accepted,
            "rejected_capabilities": rejected,
            "effective_max_cleanup_concurrency": 0,
            "resolved_work_queues": [
                {"id": work_queue.id, "name": work_queue.name}
                for work_queue in work_queues
            ],
            "initial_snapshot": initial_snapshot,
        },
    )


async def _persist_worker_channel_heartbeat(
    session: AsyncSession,
    work_pool_name: str,
    frame: WorkerHeartbeatFrame,
) -> None:
    work_pool = await models.workers.read_work_pool_by_name(
        session=session,
        work_pool_name=work_pool_name,
    )
    if work_pool is None:
        raise RuntimeError("Worker channel work pool no longer exists")

    await models.workers.record_worker_heartbeat(
        session=session,
        work_pool=work_pool,
        worker_name=frame.payload.worker_name,
        heartbeat_interval_seconds=frame.payload.heartbeat_interval_seconds,
        emit_status_change=emit_work_pool_status_event,
    )


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
        state_ts = run.state_timestamp
        return schemas.responses.FlowRunSlotSummary(
            id=run.id,
            name=run.name,
            state_type=run.state_type if run.state_type else None,
            state_name=run.state_name if run.state_name else None,
            start_time=run.start_time,
            state_timestamp=state_ts,
            time_in_current_state=((current_time - state_ts) if state_ts else None),
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


@router.websocket("/{work_pool_name}/workers/connect")
async def worker_channel_connect(
    websocket: WebSocket,
    work_pool_name: str = Path(..., description="The work pool name"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    websocket = await subscriptions.accept_prefect_socket(
        websocket,
        require_prefect_subprotocol=True,
        authentication_failed_reason=WorkerChannelCloseReason.AUTHENTICATION_FAILED.value,
    )
    if not websocket:
        return

    try:
        hello = await _receive_worker_hello(websocket)
        async with db.session_context(begin_transaction=True) as session:
            ready = await _build_worker_ready_frame(
                session=session,
                work_pool_name=work_pool_name,
                hello=hello,
            )

        await websocket.send_json(ready.model_dump(mode="json"))

        while True:
            try:
                message = await websocket.receive_json()
                frame = validate_worker_channel_frame(message)
            except ValidationError:
                await _close_worker_channel(
                    websocket, WorkerChannelCloseReason.PROTOCOL_ERROR
                )
                return
            except ValueError:
                await _close_worker_channel(
                    websocket, WorkerChannelCloseReason.PROTOCOL_ERROR
                )
                return

            if not isinstance(frame, WorkerHeartbeatFrame):
                await _close_worker_channel(
                    websocket, WorkerChannelCloseReason.PROTOCOL_ERROR
                )
                return

            if (
                frame.payload.consumer_id != hello.payload.consumer_id
                or frame.payload.worker_name != hello.payload.worker_name
            ):
                await _close_worker_channel(
                    websocket, WorkerChannelCloseReason.PROTOCOL_ERROR
                )
                return

            try:
                async with db.session_context(begin_transaction=True) as session:
                    await _persist_worker_channel_heartbeat(
                        session=session,
                        work_pool_name=work_pool_name,
                        frame=frame,
                    )
            except Exception:
                logger.exception("Worker channel heartbeat persistence failed")
                await _close_worker_channel(
                    websocket,
                    WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED,
                )
                return

    except WorkerChannelSetupError as exc:
        logger.info("Worker channel setup failed: %s", exc.detail)
        await _close_worker_channel(websocket, exc.close_reason)
    except HTTPException as exc:
        logger.info("Worker channel setup failed HTTP validation: %s", exc.detail)
        await _close_worker_channel(websocket, WorkerChannelCloseReason.PROTOCOL_ERROR)
    except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:
        return
    except Exception:
        logger.exception("Worker channel setup failed due to a transient server error")
        await _close_worker_channel(
            websocket, WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR
        )


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

        await models.workers.record_worker_heartbeat(
            session=session,
            work_pool=work_pool,
            worker_name=name,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
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
