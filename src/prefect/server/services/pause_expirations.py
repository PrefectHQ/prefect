"""
The FailExpiredPauses service. Responsible for putting Paused flow runs in a Failed state if they are not resumed on time.
"""

import asyncio
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from docket import Depends as DocketDepends
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.database.dependencies import db_injector
from prefect.server.database.orm_models import FlowRun
from prefect.server.schemas import states
from prefect.server.services.base import LoopService
from prefect.settings import PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import now


# Docket task function for failing a single expired paused flow run
async def fail_expired_pause(
    *,
    db: PrefectDBInterface = DocketDepends(provide_database_interface),
    flow_run_id: UUID,
    pause_timeout: str,
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


class FailExpiredPauses(LoopService):
    """
    Fails flow runs that have been paused and never resumed
    """

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.pause_expirations

    def __init__(self, loop_seconds: Optional[float] = None, **kwargs: Any):
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS.value(),
            **kwargs,
        )

        # query for this many runs to mark failed at once
        self.batch_size = 200

    async def _on_start(self) -> None:
        """Register docket task if docket is available."""
        await super()._on_start()
        if self.docket is not None:
            self.docket.register(fail_expired_pause)

    @db_injector
    async def run_once(self, db: PrefectDBInterface) -> None:
        """
        Mark flow runs as failed by:

        - Querying for flow runs in a Paused state that have timed out
        - For any runs past the "expiration" threshold, setting the flow run state to a
          new `Failed` state
        """
        if self.docket is not None:
            # Use docket to schedule tasks
            async with db.session_context() as session:
                query = (
                    sa.select(db.FlowRun)
                    .where(
                        db.FlowRun.state_type == states.StateType.PAUSED,
                    )
                    .limit(self.batch_size)
                )

                result = await session.execute(query)
                runs = result.scalars().all()

                # Schedule each run to be marked failed via docket
                for run in runs:
                    if (
                        run.state is not None
                        and run.state.state_details.pause_timeout is not None
                        and run.state.state_details.pause_timeout < now("UTC")
                    ):
                        await self.docket.add(fail_expired_pause)(
                            run.id, str(run.state.state_details.pause_timeout)
                        )

                self.logger.info(f"Scheduled {len(runs)} expired pause tasks.")
        else:
            # Fall back to inline execution
            while True:
                async with db.session_context(begin_transaction=True) as session:
                    query = (
                        sa.select(db.FlowRun)
                        .where(
                            db.FlowRun.state_type == states.StateType.PAUSED,
                        )
                        .limit(self.batch_size)
                    )

                    result = await session.execute(query)
                    runs = result.scalars().all()

                    # mark each run as failed
                    for run in runs:
                        await self._mark_flow_run_as_failed(
                            session=session, flow_run=run
                        )

                    # if no runs were found, exit the loop
                    if len(runs) < self.batch_size:
                        break

            self.logger.info("Finished monitoring for expired pauses.")

    async def _mark_flow_run_as_failed(
        self, session: AsyncSession, flow_run: FlowRun
    ) -> None:
        """
        Mark a flow run as failed.

        Pass-through method for overrides.
        """
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


if __name__ == "__main__":
    asyncio.run(FailExpiredPauses(handle_signals=True).start())
