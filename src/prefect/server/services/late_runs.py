"""
The MarkLateRuns service. Responsible for putting flow runs in a Late state if they are not started on time.
The threshold for a late run can be configured by changing `PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Logged, Perpetual

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.orchestration.core_policy import MarkLateRunsPolicy
from prefect.server.schemas import states
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now


async def mark_flow_run_late(
    flow_run_id: Annotated[UUID, Logged],
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Mark a single flow run as late (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        result = await session.execute(
            sa.select(db.FlowRun.id, db.FlowRun.next_scheduled_start_time).where(
                db.FlowRun.id == flow_run_id
            )
        )
        flow_run = result.one_or_none()

        if not flow_run:
            return

        try:
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=states.Late(scheduled_time=flow_run.next_scheduled_start_time),
                flow_policy=MarkLateRunsPolicy,  # type: ignore
            )
        except ObjectNotFoundError:
            return


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.late_runs.enabled,
)
async def monitor_late_runs(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.late_runs.loop_seconds
        ),
    ),
) -> None:
    """Monitor for late flow runs and schedule marking tasks."""
    settings = get_current_settings().server.services.late_runs
    batch_size = 400
    scheduled_to_start_before = now("UTC") - settings.after_seconds

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

        for run in runs:
            await docket.add(mark_flow_run_late)(run.id)
