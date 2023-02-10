"""
The CancellationCleanup service. Responsible for cancelling tasks and subflows that haven't finished.
"""

import asyncio

import pendulum
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import or_

import prefect.server.models as models
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.schemas import filters, states
from prefect.server.services.loop_service import LoopService
from prefect.settings import PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS

NON_TERMINAL_STATES = list(set(states.StateType) - states.TERMINAL_STATES)


class CancellationCleanup(LoopService):
    """
    A simple loop service responsible for cancelling tasks and subflows left over from
    cancelling flow runs
    """

    def __init__(self, loop_seconds: float = None, **kwargs):
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS.value(),
            **kwargs,
        )

        # query for this many runs to mark failed at once
        self.batch_size = 200

    @inject_db
    async def run_once(self, db: PrefectDBInterface):
        """
        - cancels active tasks belonging to recently cancelled flow runs
        - cancels any active subflow that belongs to a cancelled flow
        """
        async with db.session_context(begin_transaction=True) as session:
            # cancels active tasks belonging to recently cancelled flow runs
            await self.clean_up_cancelled_flow_run_task_runs(db, session)

            # cancels any active subflow run that belongs to a cancelled flow run
            await self.clean_up_cancelled_subflow_runs(db, session)

        self.logger.info("Finished cleaning up cancelled flow runs.")

    async def clean_up_cancelled_flow_run_task_runs(self, db, session):
        while True:
            cancelled_flow_query = (
                sa.select(db.FlowRun)
                .where(
                    db.FlowRun.state_type == states.StateType.CANCELLED,
                    db.FlowRun.end_time != None,
                    db.FlowRun.end_time >= (pendulum.now("UTC").subtract(days=1)),
                )
                .limit(self.batch_size)
            )

            flow_run_result = await session.execute(cancelled_flow_query)
            flow_runs = flow_run_result.scalars().all()

            for run in flow_runs:
                await self._cancel_child_runs(session=session, flow_run=run)

            # if no relevant flows were found, exit the loop
            if len(flow_runs) < self.batch_size:
                break

    async def clean_up_cancelled_subflow_runs(self, db, session):
        while True:
            subflow_query = (
                sa.select(db.FlowRun)
                .where(
                    or_(
                        db.FlowRun.state_type == states.StateType.PENDING,
                        db.FlowRun.state_type == states.StateType.SCHEDULED,
                        db.FlowRun.state_type == states.StateType.RUNNING,
                        db.FlowRun.state_type == states.StateType.PAUSED,
                        db.FlowRun.state_type == states.StateType.CANCELLING,
                    ),
                    db.FlowRun.parent_task_run_id != None,
                )
                .limit(self.batch_size)
            )

            subflow_run_result = await session.execute(subflow_query)
            subflow_runs = subflow_run_result.scalars().all()

            for subflow_run in subflow_runs:
                await self._cancel_subflows(session=session, flow_run=subflow_run)

            # if no relevant flows were found, exit the loop
            if len(subflow_runs) < self.batch_size:
                break

    async def _cancel_child_runs(
        self, session: AsyncSession, flow_run: PrefectDBInterface.FlowRun
    ) -> None:
        child_task_runs = await models.task_runs.read_task_runs(
            session,
            flow_run_filter=filters.FlowRunFilter(id={"any_": [flow_run.id]}),
            task_run_filter=filters.TaskRunFilter(
                state={"type": {"any_": NON_TERMINAL_STATES}}
            ),
            limit=100,
        )

        for task_run in child_task_runs:
            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=states.Cancelled(message="The parent flow run was cancelled."),
                force=True,
            )

    async def _cancel_subflows(
        self, session: AsyncSession, flow_run: PrefectDBInterface.FlowRun
    ) -> None:
        if not flow_run.parent_task_run_id:
            return

        parent_task_run = await models.task_runs.read_task_run(
            session, task_run_id=flow_run.parent_task_run_id
        )
        containing_flow_run = await models.flow_runs.read_flow_run(
            session, flow_run_id=parent_task_run.flow_run_id
        )

        if containing_flow_run.state.type == states.StateType.CANCELLED:
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=states.Cancelled(message="The parent flow run was cancelled."),
                force=True,
            )


if __name__ == "__main__":
    asyncio.run(CancellationCleanup().start())
