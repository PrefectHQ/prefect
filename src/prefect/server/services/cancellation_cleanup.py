"""
The CancellationCleanup service. Responsible for cancelling tasks and subflows that haven't finished.
"""

import datetime
import logging
from typing import Annotated, Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Logged, Perpetual
from sqlalchemy.sql.expression import or_

import prefect.server.models as models
from prefect.client.schemas.worker_channel import CANCELLING_TIMEOUT_TEARDOWN
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.schemas import filters, responses, states
from prefect.server.services.perpetual_services import perpetual_service
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueMessage,
    WorkerCleanupQueue,
    get_worker_cleanup_queue,
)
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now

NON_TERMINAL_STATES = list(set(states.StateType) - states.TERMINAL_STATES)
CANCELLING_TIMEOUT_CANCELLED_MESSAGE = (
    "Flow run cancellation timed out; marked this flow run as Cancelled."
)
CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY = (
    "__prefect_cancelling_timeout_cleanup_state_id"
)
IN_MEMORY_CLEANUP_QUEUE_STORAGE = (
    "prefect.server.worker_communication.cleanup_queue.memory"
)
IN_MEMORY_CLEANUP_QUEUE_MARKER_TOKEN = uuid4()
logger: logging.Logger = get_logger(__name__)

_service_cleanup_queue: WorkerCleanupQueue | None = None
_service_cleanup_queue_storage: str | None = None


def _get_service_worker_cleanup_queue() -> WorkerCleanupQueue:
    global _service_cleanup_queue, _service_cleanup_queue_storage

    storage = get_current_settings().server.worker_channel.cleanup_queue_storage
    if _service_cleanup_queue is None or _service_cleanup_queue_storage != storage:
        _service_cleanup_queue = get_worker_cleanup_queue()
        _service_cleanup_queue_storage = storage

    return _service_cleanup_queue


def _mark_cancelling_timeout_cleanup_complete(
    flow_run: Any, cleanup_state_id: UUID
) -> None:
    flow_run.context = {
        **(flow_run.context or {}),
        CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY: (
            _cancelling_timeout_cleanup_marker_value(cleanup_state_id)
        ),
    }


def _uses_in_memory_cleanup_queue_storage() -> bool:
    return (
        get_current_settings().server.worker_channel.cleanup_queue_storage
        == IN_MEMORY_CLEANUP_QUEUE_STORAGE
    )


def _cancelling_timeout_cleanup_marker_value(cleanup_state_id: UUID) -> str:
    if _uses_in_memory_cleanup_queue_storage():
        return f"{cleanup_state_id}:{IN_MEMORY_CLEANUP_QUEUE_MARKER_TOKEN}"
    return str(cleanup_state_id)


def _cancelling_timeout_cleanup_marker_expression(
    db: PrefectDBInterface,
) -> sa.ColumnElement[str]:
    marker = sa.cast(db.FlowRun.state_id, sa.String)
    if db.dialect.name == "sqlite":
        marker_hex = sa.func.replace(marker, "-", "")
        marker = sa.func.printf(
            "%s-%s-%s-%s-%s",
            sa.func.substr(marker_hex, 1, 8),
            sa.func.substr(marker_hex, 9, 4),
            sa.func.substr(marker_hex, 13, 4),
            sa.func.substr(marker_hex, 17, 4),
            sa.func.substr(marker_hex, 21, 12),
        )
    if _uses_in_memory_cleanup_queue_storage():
        return marker + f":{IN_MEMORY_CLEANUP_QUEUE_MARKER_TOKEN}"
    return marker


# Docket task function for cancelling child task runs of a cancelled flow run
async def cancel_child_task_runs(
    flow_run_id: Annotated[UUID, Logged],
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Cancel child task runs of a cancelled flow run (docket task)."""
    async with db.session_context() as session:
        child_task_runs = await models.task_runs.read_task_runs(
            session,
            flow_run_filter=filters.FlowRunFilter(
                id=filters.FlowRunFilterId(any_=[flow_run_id])
            ),
            task_run_filter=filters.TaskRunFilter(
                state=filters.TaskRunFilterState(
                    type=filters.TaskRunFilterStateType(any_=NON_TERMINAL_STATES)
                )
            ),
            limit=100,
        )

    for task_run in child_task_runs:
        async with db.session_context(begin_transaction=True) as session:
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=states.Cancelled(message="The parent flow run was cancelled."),
                force=True,
            )


# Docket task function for cancelling a subflow run whose parent was cancelled
async def cancel_subflow_run(
    subflow_run_id: Annotated[UUID, Logged],
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Cancel a subflow run whose parent flow run was cancelled (docket task)."""
    async with db.session_context() as session:
        flow_run = await models.flow_runs.read_flow_run(
            session, flow_run_id=subflow_run_id
        )

        if not flow_run or not flow_run.parent_task_run_id or not flow_run.state:
            return

        if flow_run.state.type in states.TERMINAL_STATES:
            return

        parent_task_run = await models.task_runs.read_task_run(
            session, task_run_id=flow_run.parent_task_run_id
        )

        if not parent_task_run or not parent_task_run.flow_run_id:
            return

        containing_flow_run = await models.flow_runs.read_flow_run(
            session, flow_run_id=parent_task_run.flow_run_id
        )

        if (
            containing_flow_run
            and containing_flow_run.state
            and containing_flow_run.state.type != states.StateType.CANCELLED
        ):
            return

        if flow_run.deployment_id:
            state = states.Cancelling(message="The parent flow run was cancelled.")
        else:
            state = states.Cancelled(message="The parent flow run was cancelled.")

    async with db.session_context(begin_transaction=True) as session:
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=subflow_run_id,
            state=state,
        )


@perpetual_service(
    enabled_getter=lambda: (
        get_current_settings().server.services.cancellation_cleanup.enabled
    ),
)
async def enqueue_cancelling_timeout_teardowns(
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
    cleanup_queue: WorkerCleanupQueue = Depends(_get_service_worker_cleanup_queue),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=datetime.timedelta(
            seconds=get_current_settings().server.services.cancellation_cleanup.loop_seconds
        ),
    ),
) -> list[CleanupQueueMessage]:
    """Enqueue worker cleanup for flow runs stuck in CANCELLING past the timeout."""
    settings = get_current_settings().server.services.cancellation_cleanup
    batch_size = 200
    cutoff = now("UTC") - datetime.timedelta(
        seconds=settings.cancelling_timeout_seconds
    )
    enqueued_messages: list[CleanupQueueMessage] = []
    last_seen: tuple[datetime.datetime, UUID] | None = None
    while True:
        cleanup_state_id_marker = db.FlowRun.context[
            CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY
        ].as_string()
        cleanup_state_id_marker_value = _cancelling_timeout_cleanup_marker_expression(
            db
        )
        candidate_query = (
            sa.select(db.FlowRun.state_timestamp, db.FlowRun.id)
            .outerjoin(db.FlowRunState, db.FlowRun.state_id == db.FlowRunState.id)
            .where(
                db.FlowRun.state_timestamp.is_not(None),
                or_(
                    sa.and_(
                        db.FlowRun.state_type == states.StateType.CANCELLING,
                        db.FlowRun.state_timestamp <= cutoff,
                    ),
                    sa.and_(
                        db.FlowRun.state_type == states.StateType.CANCELLED,
                        db.FlowRunState.message == CANCELLING_TIMEOUT_CANCELLED_MESSAGE,
                        or_(
                            db.FlowRun.context.is_(None),
                            cleanup_state_id_marker.is_(None),
                            cleanup_state_id_marker != cleanup_state_id_marker_value,
                        ),
                    ),
                ),
            )
            .order_by(db.FlowRun.state_timestamp, db.FlowRun.id)
            .limit(batch_size)
        )
        if last_seen is not None:
            last_seen_timestamp, last_seen_id = last_seen
            candidate_query = candidate_query.where(
                or_(
                    db.FlowRun.state_timestamp > last_seen_timestamp,
                    sa.and_(
                        db.FlowRun.state_timestamp == last_seen_timestamp,
                        db.FlowRun.id > last_seen_id,
                    ),
                )
            )

        async with db.session_context() as session:
            result = await session.execute(candidate_query)
        candidates = result.all()
        if not candidates:
            break

        for state_timestamp, flow_run_id in candidates:
            cleanup_enqueue_parameters: dict[str, Any] | None = None
            cleanup_state_id: UUID | None = None
            async with db.session_context(begin_transaction=True) as session:
                flow_run_result = await session.execute(
                    sa.select(
                        db.FlowRun,
                        db.WorkQueue.work_pool_id,
                        db.FlowRunState.message,
                    )
                    .outerjoin(
                        db.WorkQueue, db.FlowRun.work_queue_id == db.WorkQueue.id
                    )
                    .outerjoin(
                        db.FlowRunState, db.FlowRun.state_id == db.FlowRunState.id
                    )
                    .where(db.FlowRun.id == flow_run_id)
                    .with_for_update(of=db.FlowRun)
                )
                row = flow_run_result.first()
                if row is None:
                    continue

                flow_run, work_pool_id, state_message = row
                if flow_run.state_type == states.StateType.CANCELLING:
                    if (
                        flow_run.state_id is None
                        or flow_run.state_timestamp is None
                        or flow_run.state_timestamp > cutoff
                    ):
                        continue

                    try:
                        state_result = await models.flow_runs.set_flow_run_state(
                            session=session,
                            flow_run_id=flow_run.id,
                            state=states.Cancelled(
                                message=CANCELLING_TIMEOUT_CANCELLED_MESSAGE
                            ),
                        )
                    except ObjectNotFoundError:
                        continue

                    if state_result.status != responses.SetStateStatus.ACCEPT:
                        logger.info(
                            "CANCELLING timeout state transition for flow run %s was "
                            "not accepted",
                            flow_run.id,
                            extra={
                                "status": state_result.status.value,
                                "reason": getattr(state_result.details, "reason", None),
                            },
                        )
                        continue

                    if (
                        state_result.state is None
                        or state_result.state.id is None
                        or state_result.state.type != states.StateType.CANCELLED
                    ):
                        continue

                    cleanup_state_id = state_result.state.id
                elif flow_run.state_type == states.StateType.CANCELLED:
                    cleanup_state_id = flow_run.state_id
                    if (
                        cleanup_state_id is None
                        or state_message != CANCELLING_TIMEOUT_CANCELLED_MESSAGE
                        or (flow_run.context or {}).get(
                            CANCELLING_TIMEOUT_CLEANUP_STATE_ID_CONTEXT_KEY
                        )
                        == _cancelling_timeout_cleanup_marker_value(cleanup_state_id)
                    ):
                        continue
                else:
                    continue

                if flow_run.work_queue_id is None or work_pool_id is None:
                    logger.warning(
                        "Skipping CANCELLING timeout cleanup for unroutable flow run: "
                        "flow_run_id=%s work_queue_id=%s",
                        flow_run.id,
                        flow_run.work_queue_id,
                    )
                    if cleanup_state_id is not None:
                        _mark_cancelling_timeout_cleanup_complete(
                            flow_run, cleanup_state_id
                        )
                    continue

                cleanup_enqueue_parameters = {
                    "message_id": uuid5(
                        NAMESPACE_URL,
                        "prefect:"
                        f"{CANCELLING_TIMEOUT_TEARDOWN}:"
                        f"{flow_run.id}:{cleanup_state_id}",
                    ),
                    "idempotency_key": (
                        f"{CANCELLING_TIMEOUT_TEARDOWN}:"
                        f"{flow_run.id}:{cleanup_state_id}"
                    ),
                    "work_pool_id": work_pool_id,
                    "work_queue_id": flow_run.work_queue_id,
                    "kind": CANCELLING_TIMEOUT_TEARDOWN,
                    "target": {
                        "flow_run_id": str(flow_run.id),
                        "infrastructure_pid": flow_run.infrastructure_pid,
                    },
                }

            if cleanup_enqueue_parameters is not None:
                message = await cleanup_queue.enqueue(**cleanup_enqueue_parameters)
                enqueued_messages.append(message)
                if cleanup_state_id is not None:
                    async with db.session_context(begin_transaction=True) as session:
                        marker_flow_run = await models.flow_runs.read_flow_run(
                            session=session,
                            flow_run_id=flow_run_id,
                            for_update=True,
                        )
                        if (
                            marker_flow_run is not None
                            and marker_flow_run.state_id == cleanup_state_id
                        ):
                            _mark_cancelling_timeout_cleanup_complete(
                                marker_flow_run, cleanup_state_id
                            )

        last_state_timestamp, last_flow_run_id = candidates[-1]
        last_seen = (last_state_timestamp, last_flow_run_id)
        if len(candidates) < batch_size:
            break

    if enqueued_messages:
        logger.info(
            "Enqueued CANCELLING timeout cleanup messages: count=%s",
            len(enqueued_messages),
        )

    return enqueued_messages


# Perpetual monitor for cancelled flow runs with child tasks (find and flood pattern)
@perpetual_service(
    enabled_getter=lambda: (
        get_current_settings().server.services.cancellation_cleanup.enabled
    ),
)
async def monitor_cancelled_flow_runs(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=datetime.timedelta(
            seconds=get_current_settings().server.services.cancellation_cleanup.loop_seconds
        ),
    ),
) -> None:
    """Monitor for cancelled flow runs and schedule child task cancellation."""

    batch_size = 200
    cancelled_flow_query = (
        sa.select(db.FlowRun.id)
        .where(
            db.FlowRun.state_type == states.StateType.CANCELLED,
            db.FlowRun.end_time.is_not(None),
            db.FlowRun.end_time >= (now("UTC") - datetime.timedelta(days=1)),
        )
        .order_by(db.FlowRun.id)
        .limit(batch_size)
    )

    async with db.session_context() as session:
        flow_run_result = await session.execute(cancelled_flow_query)
    flow_run_ids = flow_run_result.scalars().all()

    for flow_run_id in flow_run_ids:
        await docket.add(cancel_child_task_runs)(flow_run_id)


# Perpetual monitor for subflow runs that need cancellation (find and flood pattern)
@perpetual_service(
    enabled_getter=lambda: (
        get_current_settings().server.services.cancellation_cleanup.enabled
    ),
)
async def monitor_subflow_runs(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=datetime.timedelta(
            seconds=get_current_settings().server.services.cancellation_cleanup.loop_seconds
        ),
    ),
) -> None:
    """Monitor for subflow runs that need to be cancelled."""

    batch_size = 200
    subflow_query = (
        sa.select(db.FlowRun.id)
        .where(
            or_(
                db.FlowRun.state_type == states.StateType.PENDING,
                db.FlowRun.state_type == states.StateType.SCHEDULED,
                db.FlowRun.state_type == states.StateType.RUNNING,
                db.FlowRun.state_type == states.StateType.PAUSED,
                db.FlowRun.state_type == states.StateType.CANCELLING,
            ),
            db.FlowRun.parent_task_run_id.is_not(None),
        )
        .order_by(db.FlowRun.id)
        .limit(batch_size)
    )

    async with db.session_context() as session:
        subflow_run_result = await session.execute(subflow_query)
    subflow_run_ids = subflow_run_result.scalars().all()

    for subflow_run_id in subflow_run_ids:
        await docket.add(cancel_subflow_run)(subflow_run_id)
