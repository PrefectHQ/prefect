"""
The MarkLateRuns service. Responsible for putting flow runs in a Late state if they are not started on time.
The threshold for a late run can be configured by changing `PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS`.
"""

from __future__ import annotations

import datetime
from datetime import timedelta
from uuid import UUID

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Perpetual

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.orchestration.core_policy import MarkLateRunsPolicy
from prefect.server.schemas import states
from prefect.settings import (
    PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS,
    PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS,
)
from prefect.types._datetime import now


# Docket task function for marking a single flow run as late
async def mark_flow_run_late(
    flow_run_id: UUID,
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Mark a single flow run as late (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        # Get the flow run to retrieve its scheduled time
        result = await session.execute(
            sa.select(db.FlowRun.id, db.FlowRun.next_scheduled_start_time).where(
                db.FlowRun.id == flow_run_id
            )
        )
        flow_run = result.one_or_none()

        if not flow_run:
            return  # Flow run was deleted

        try:
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=states.Late(scheduled_time=flow_run.next_scheduled_start_time),
                flow_policy=MarkLateRunsPolicy,  # type: ignore
            )
        except ObjectNotFoundError:
            return  # Flow run was deleted during processing


# Perpetual monitor for late flow runs (find and flood pattern)
async def monitor_late_runs(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(seconds=PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS.value()),
    ),
) -> None:
    """Monitor for late flow runs and schedule marking tasks."""

    batch_size = 400
    mark_late_after = PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS.value()
    scheduled_to_start_before = now("UTC") - datetime.timedelta(
        seconds=mark_late_after.total_seconds()
    )

    async with db.session_context() as session:
        query = (
            sa.select(db.FlowRun.id, db.FlowRun.next_scheduled_start_time)
            .where(
                (db.FlowRun.next_scheduled_start_time <= scheduled_to_start_before),
                db.FlowRun.state_type == states.StateType.SCHEDULED,
                db.FlowRun.state_name == "Scheduled",
            )
            .limit(batch_size)
        )
        result = await session.execute(query)
        runs = result.all()

        # Schedule each run to be marked late
        for run in runs:
            await docket.add(mark_flow_run_late)(run.id)
