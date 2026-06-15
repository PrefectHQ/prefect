"""
The CancellationCleanup service. Responsible for cancelling tasks and subflows that haven't finished.
"""

import datetime
import logging
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Logged, Perpetual, Retry

import prefect.server.models as models
from prefect._internal.uuid7 import uuid7
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
CANCELLING_TIMEOUT_CHECK_KEY_PREFIX = "cancelling-timeout"
PUSH_WORK_POOL_TYPE_SUFFIX = ":push"
MANAGED_WORK_POOL_TYPE_SUFFIX = ":managed"
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


def cancelling_timeout_check_key(flow_run_id: UUID) -> str:
    return f"{CANCELLING_TIMEOUT_CHECK_KEY_PREFIX}:{flow_run_id}"


async def schedule_cancelling_timeout_check(
    *,
    docket: Docket,
    flow_run_id: UUID,
    flow_run_state_id: UUID,
    when: datetime.datetime,
) -> None:
    await docket.replace(
        handle_cancelling_timeout,
        key=cancelling_timeout_check_key(flow_run_id),
        when=when,
    )(
        flow_run_id=flow_run_id,
        flow_run_state_id=flow_run_state_id,
        timeout_cancelled_state_id=uuid7(),
    )


async def schedule_cancelling_timeout_check_for_state(
    *,
    docket: Docket,
    flow_run_id: UUID,
    state: states.State | None,
) -> None:
    settings = get_current_settings().server.services.cancellation_cleanup
    if (
        not settings.enabled
        or state is None
        or state.type != states.StateType.CANCELLING
        or state.id is None
        or state.timestamp is None
    ):
        return

    await schedule_cancelling_timeout_check(
        docket=docket,
        flow_run_id=flow_run_id,
        flow_run_state_id=state.id,
        when=state.timestamp
        + datetime.timedelta(seconds=settings.cancelling_timeout_seconds),
    )


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
    docket: Docket = CurrentDocket(),
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

        if (
            flow_run.deployment_id
            and flow_run.state.type == states.StateType.CANCELLING
        ):
            return

        if flow_run.deployment_id:
            state = states.Cancelling(message="The parent flow run was cancelled.")
        else:
            state = states.Cancelled(message="The parent flow run was cancelled.")

    async with db.session_context(begin_transaction=True) as session:
        state_result = await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=subflow_run_id,
            state=state,
        )

    if state_result.status == responses.SetStateStatus.ACCEPT:
        await schedule_cancelling_timeout_check_for_state(
            docket=docket,
            flow_run_id=subflow_run_id,
            state=state_result.state,
        )


async def handle_cancelling_timeout(
    flow_run_id: Annotated[UUID, Logged],
    flow_run_state_id: Annotated[UUID, Logged],
    timeout_cancelled_state_id: Annotated[UUID, Logged],
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
    cleanup_queue: WorkerCleanupQueue = Depends(_get_service_worker_cleanup_queue),
    retry: Retry = Retry.forever(delay=datetime.timedelta(seconds=0.5)),
) -> CleanupQueueMessage | None:
    """Handle a scheduled CANCELLING timeout check for a single flow run."""
    settings = get_current_settings().server.services.cancellation_cleanup

    async with db.session_context(begin_transaction=True) as session:
        flow_run_result = await session.execute(
            sa.select(db.FlowRun)
            .where(db.FlowRun.id == flow_run_id)
            .with_for_update(of=db.FlowRun)
        )
        flow_run = flow_run_result.scalar_one_or_none()
        if flow_run is None:
            logger.info(
                "Flow run %s no longer exists, skipping CANCELLING timeout",
                flow_run_id,
            )
            return None

        timeout_cancelled_state_already_committed = (
            flow_run.state_type == states.StateType.CANCELLED
            and flow_run.state_id == timeout_cancelled_state_id
        )
        if not timeout_cancelled_state_already_committed:
            if flow_run.state_id != flow_run_state_id:
                logger.info(
                    "Flow run %s is in a new state, skipping CANCELLING timeout",
                    flow_run.id,
                )
                return None

            if flow_run.state_type != states.StateType.CANCELLING:
                logger.info(
                    "Flow run %s is no longer CANCELLING, skipping timeout",
                    flow_run.id,
                )
                return None

            if flow_run.state_timestamp is None:
                logger.info(
                    "Flow run %s has no CANCELLING state timestamp, skipping timeout",
                    flow_run.id,
                )
                return None

            deadline = flow_run.state_timestamp + datetime.timedelta(
                seconds=settings.cancelling_timeout_seconds
            )
            if deadline > now("UTC"):
                logger.info(
                    "Flow run %s has not reached the CANCELLING timeout, rescheduling",
                    flow_run.id,
                )
                retry.at(deadline)
                return None

            try:
                from prefect.server.orchestration.core_policy import CoreFlowPolicy

                state_result = await models.flow_runs.set_flow_run_state(
                    session=session,
                    flow_run_id=flow_run.id,
                    state=states.Cancelled(
                        id=timeout_cancelled_state_id,
                        message=CANCELLING_TIMEOUT_CANCELLED_MESSAGE,
                    ),
                    flow_policy=CoreFlowPolicy,
                )
            except ObjectNotFoundError:
                logger.info(
                    "Flow run %s was removed during CANCELLING timeout, skipping",
                    flow_run.id,
                )
                return None

            if state_result.status != responses.SetStateStatus.ACCEPT:
                logger.info(
                    "CANCELLING timeout state transition for flow run %s was not "
                    "accepted",
                    flow_run.id,
                    extra={
                        "status": state_result.status.value,
                        "reason": getattr(state_result.details, "reason", None),
                    },
                )
                return None

            if (
                state_result.state is None
                or state_result.state.id != timeout_cancelled_state_id
                or state_result.state.type != states.StateType.CANCELLED
            ):
                return None

    async with db.session_context(begin_transaction=True) as session:
        flow_run_result = await session.execute(
            sa.select(
                db.FlowRun,
                db.WorkQueue.work_pool_id,
                db.WorkPool.type,
            )
            .outerjoin(db.WorkQueue, db.FlowRun.work_queue_id == db.WorkQueue.id)
            .outerjoin(db.WorkPool, db.WorkQueue.work_pool_id == db.WorkPool.id)
            .where(db.FlowRun.id == flow_run_id)
            .with_for_update(of=db.FlowRun)
        )
        row = flow_run_result.first()
        if row is None:
            logger.info(
                "Flow run %s no longer exists, skipping CANCELLING timeout cleanup",
                flow_run_id,
            )
            return None

        flow_run, work_pool_id, work_pool_type = row
        if (
            flow_run.state_type != states.StateType.CANCELLED
            or flow_run.state_id != timeout_cancelled_state_id
        ):
            logger.info(
                "Flow run %s is no longer in the timeout Cancelled state, skipping "
                "CANCELLING timeout cleanup",
                flow_run.id,
            )
            return None

        if flow_run.work_queue_id is None or work_pool_id is None:
            logger.warning(
                "Skipping CANCELLING timeout cleanup for unroutable flow run: "
                "flow_run_id=%s work_queue_id=%s",
                flow_run.id,
                flow_run.work_queue_id,
            )
            return None

        work_pool_type = str(work_pool_type) if work_pool_type else None
        if work_pool_type and work_pool_type.endswith(
            (PUSH_WORK_POOL_TYPE_SUFFIX, MANAGED_WORK_POOL_TYPE_SUFFIX)
        ):
            logger.info(
                "Skipping CANCELLING timeout cleanup for workerless work pool flow "
                "run: flow_run_id=%s work_queue_id=%s work_pool_id=%s "
                "work_pool_type=%s",
                flow_run.id,
                flow_run.work_queue_id,
                work_pool_id,
                work_pool_type,
            )
            return None

        cleanup_enqueue_parameters = {
            "message_id": uuid5(
                NAMESPACE_URL,
                "prefect:"
                f"{CANCELLING_TIMEOUT_TEARDOWN}:"
                f"{flow_run.id}:{timeout_cancelled_state_id}",
            ),
            "idempotency_key": (
                f"{CANCELLING_TIMEOUT_TEARDOWN}:"
                f"{flow_run.id}:{timeout_cancelled_state_id}"
            ),
            "work_pool_id": work_pool_id,
            "work_queue_id": flow_run.work_queue_id,
            "kind": CANCELLING_TIMEOUT_TEARDOWN,
            "target": {
                "flow_run_id": str(flow_run.id),
                "infrastructure_pid": flow_run.infrastructure_pid,
            },
        }

        message = await cleanup_queue.enqueue(**cleanup_enqueue_parameters)

    logger.info(
        "Enqueued CANCELLING timeout cleanup message: flow_run_id=%s message_id=%s",
        flow_run_id,
        message.message_id,
    )
    return message


@perpetual_service(
    enabled_getter=lambda: (
        get_current_settings().server.services.cancellation_cleanup.enabled
    ),
)
async def ensure_cancelling_timeout_checks(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=datetime.timedelta(
            seconds=get_current_settings().server.services.cancellation_cleanup.loop_seconds
        ),
    ),
) -> None:
    """Seed Docket timeout checks for flow runs already in CANCELLING."""

    settings = get_current_settings().server.services.cancellation_cleanup
    batch_size = 200
    last_state_timestamp: datetime.datetime | None = None
    last_flow_run_id: UUID | None = None

    while True:
        query_conditions = [
            db.FlowRun.state_type == states.StateType.CANCELLING,
            db.FlowRun.state_id.is_not(None),
            db.FlowRun.state_timestamp.is_not(None),
        ]
        if last_state_timestamp is not None and last_flow_run_id is not None:
            query_conditions.append(
                sa.or_(
                    db.FlowRun.state_timestamp > last_state_timestamp,
                    sa.and_(
                        db.FlowRun.state_timestamp == last_state_timestamp,
                        db.FlowRun.id > last_flow_run_id,
                    ),
                )
            )

        cancelling_flow_query = (
            sa.select(
                db.FlowRun.id,
                db.FlowRun.state_id,
                db.FlowRun.state_timestamp,
            )
            .where(*query_conditions)
            .order_by(db.FlowRun.state_timestamp, db.FlowRun.id)
            .limit(batch_size)
        )

        async with db.session_context() as session:
            result = await session.execute(cancelling_flow_query)
        cancelling_flow_runs = result.all()

        if not cancelling_flow_runs:
            break

        for flow_run_id, flow_run_state_id, state_timestamp in cancelling_flow_runs:
            await docket.add(
                handle_cancelling_timeout,
                key=cancelling_timeout_check_key(flow_run_id),
                when=state_timestamp
                + datetime.timedelta(seconds=settings.cancelling_timeout_seconds),
            )(
                flow_run_id=flow_run_id,
                flow_run_state_id=flow_run_state_id,
                timeout_cancelled_state_id=uuid7(),
            )

        last_flow_run_id, _, last_state_timestamp = cancelling_flow_runs[-1]
        if len(cancelling_flow_runs) < batch_size:
            break


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
            sa.or_(
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
