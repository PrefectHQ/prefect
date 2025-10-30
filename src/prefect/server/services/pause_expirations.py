"""
The FailExpiredPauses service. Responsible for putting Paused flow runs in a Failed state if they are not resumed on time.
"""

from datetime import timedelta
from uuid import UUID

import sqlalchemy as sa
from docket import CurrentDocket, Depends, Docket, Perpetual

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas import states
from prefect.settings import PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS
from prefect.types._datetime import now


# Docket task function for failing a single expired paused flow run
async def fail_expired_pause(
    flow_run_id: UUID,
    pause_timeout: str,
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Mark a single expired paused flow run as failed (docket task)."""
    async with db.session_context(begin_transaction=True) as session:
        # Re-fetch the flow run to check current state
        result = await session.execute(
            sa.select(db.FlowRun).where(db.FlowRun.id == flow_run_id)
        )
        flow_run = result.scalar_one_or_none()

        if not flow_run:
            return  # Flow run was deleted

        # Check if still paused and past timeout
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


# Perpetual monitor for expired paused flow runs (find and flood pattern)
async def monitor_expired_pauses(
    docket: Docket = CurrentDocket(),
    db: PrefectDBInterface = Depends(provide_database_interface),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS.value()
        ),
    ),
) -> None:
    """Monitor for expired paused flow runs and schedule failure tasks."""

    batch_size = 200
    async with db.session_context() as session:
        query = (
            sa.select(db.FlowRun)
            .where(
                db.FlowRun.state_type == states.StateType.PAUSED,
            )
            .limit(batch_size)
        )

        result = await session.execute(query)
        runs = result.scalars().all()

        # Schedule each expired run to be marked failed
        for run in runs:
            if (
                run.state is not None
                and run.state.state_details.pause_timeout is not None
                and run.state.state_details.pause_timeout < now("UTC")
            ):
                await docket.add(fail_expired_pause)(
                    run.id, str(run.state.state_details.pause_timeout)
                )
