"""
The CancellationCleanup service. Responsible for cancelling tasks and subflows that haven't finished.
"""

import datetime
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Logged, Perpetual
from sqlalchemy.sql.expression import or_

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas import filters, states
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now

NON_TERMINAL_STATES = list(set(states.StateType) - states.TERMINAL_STATES)


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


# Perpetual monitor for cancelled flow runs with child tasks (find and flood pattern)
@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.cancellation_cleanup.enabled,
)
async def monitor_cancelled_flow_runs(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=False,
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
    enabled_getter=lambda: get_current_settings().server.services.cancellation_cleanup.enabled,
)
async def monitor_subflow_runs(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=False,
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
