"""
The FailExpiredPauses service. Responsible for putting Paused flow runs in a Failed state if they are not resumed on time.
"""

import asyncio
from typing import Optional

import pendulum
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import states
from prefect.server.services.loop_service import LoopService
from prefect.settings import PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS


class FailExpiredPauses(LoopService):
    """
    A simple loop service responsible for identifying Paused flow runs that no longer can be resumed.
    """

    def __init__(self, loop_seconds: Optional[float] = None, **kwargs):
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_LOOP_SECONDS.value(),
            **kwargs,
        )

        # query for this many runs to mark failed at once
        self.batch_size = 200

    @inject_db
    async def run_once(self, db: PrefectDBInterface):
        """
        Mark flow runs as failed by:

        - Querying for flow runs in a Paused state that have timed out
        - For any runs past the "expiration" threshold, setting the flow run state to a new `Failed` state
        """
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
                    await self._mark_flow_run_as_failed(session=session, flow_run=run)

                # if no runs were found, exit the loop
                if len(runs) < self.batch_size:
                    break

        self.logger.info("Finished monitoring for late runs.")

    async def _mark_flow_run_as_failed(
        self, session: AsyncSession, flow_run: PrefectDBInterface.FlowRun
    ) -> None:
        """
        Mark a flow run as failed.

        Pass-through method for overrides.
        """
        if flow_run.state.state_details.pause_timeout < pendulum.now("UTC"):
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=states.Failed(message="The flow was paused and never resumed."),
                force=True,
            )


if __name__ == "__main__":
    asyncio.run(FailExpiredPauses(handle_signals=True).start())
