"""
The FailExpiredPauses service. Responsible for putting Paused flow runs in a Failed state if they are not resumed on time.
"""

from datetime import timedelta
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Logged, Perpetual

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas import states
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings
from prefect.types._datetime import now


async def fail_expired_pause(
    flow_run_id: Annotated[UUID, Logged],
    pause_timeout: Annotated[str, Logged],
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Mark a single expired paused flow run as failed (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        result = await session.execute(
            sa.select(db.FlowRun).where(db.FlowRun.id == flow_run_id)
        )
        flow_run = result.scalar_one_or_none()

        if not flow_run:
            return

        if (
            flow_run.state is not None
            and flow_run.state.state_details.pause_timeout is not None
            and flow_run.state.state_details.pause_timeout < now("UTC")
        ):
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=states.Failed(message="The flow was paused and never resumed."),
                force=True,
            )


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.pause_expirations.enabled,
)
async def monitor_expired_pauses(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.pause_expirations.loop_seconds
        ),
    ),
) -> None:
    """Monitor for expired paused flow runs and schedule failure tasks."""
    batch_size = 200

    async with db.session_context() as session:
        query = (
            sa.select(db.FlowRun)
            .where(db.FlowRun.state_type == states.StateType.PAUSED)
            .limit(batch_size)
        )

        result = await session.execute(query)
        runs = result.scalars().all()

        for run in runs:
            if (
                run.state is not None
                and run.state.state_details.pause_timeout is not None
                and run.state.state_details.pause_timeout < now("UTC")
            ):
                await docket.add(fail_expired_pause)(
                    run.id, str(run.state.state_details.pause_timeout)
                )
