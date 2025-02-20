"""
The CancellationCleanup service. Responsible for cancelling tasks and subflows that haven't finished.
"""

import asyncio
import datetime
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.sql.expression import or_

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.schemas import filters, states
from prefect.server.services.base import LoopService
from prefect.settings import PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import now

NON_TERMINAL_STATES = list(set(states.StateType) - states.TERMINAL_STATES)


class CancellationCleanup(LoopService):
    """
    Cancels tasks and subflows of flow runs that have been cancelled
    """

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.cancellation_cleanup

    def __init__(self, loop_seconds: Optional[float] = None, **kwargs: Any):
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_API_SERVICES_CANCELLATION_CLEANUP_LOOP_SECONDS.value(),
            **kwargs,
        )

        # query for this many runs to mark failed at once
        self.batch_size = 200

    @db_injector
    async def run_once(self, db: PrefectDBInterface) -> None:
        """
        - cancels active tasks belonging to recently cancelled flow runs
        - cancels any active subflow that belongs to a cancelled flow
        """
        # cancels active tasks belonging to recently cancelled flow runs
        await self.clean_up_cancelled_flow_run_task_runs(db)

        # cancels any active subflow run that belongs to a cancelled flow run
        await self.clean_up_cancelled_subflow_runs(db)

        self.logger.info("Finished cleaning up cancelled flow runs.")

    async def clean_up_cancelled_flow_run_task_runs(
        self, db: PrefectDBInterface
    ) -> None:
        while True:
            cancelled_flow_query = (
                sa.select(db.FlowRun)
                .where(
                    db.FlowRun.state_type == states.StateType.CANCELLED,
                    db.FlowRun.end_time.is_not(None),
                    db.FlowRun.end_time >= (now("UTC") - datetime.timedelta(days=1)),
                )
                .limit(self.batch_size)
            )

            async with db.session_context() as session:
                flow_run_result = await session.execute(cancelled_flow_query)
            flow_runs = flow_run_result.scalars().all()

            for run in flow_runs:
                await self._cancel_child_runs(db=db, flow_run=run)

            # if no relevant flows were found, exit the loop
            if len(flow_runs) < self.batch_size:
                break

    async def clean_up_cancelled_subflow_runs(self, db: PrefectDBInterface) -> None:
        high_water_mark = UUID(int=0)
        while True:
            # Performance optimization: Load only required columns while maintaining ORM functionality
            # Required columns:
            # - id: for high water mark tracking
            # - state_type: for state validation
            # - parent_task_run_id: for parent task run checks
            # - deployment_id: for determining cancellation state type
            subflow_query = (
                sa.select(db.FlowRun)
                .options(
                    sa.orm.load_only(
                        db.FlowRun.id,
                        db.FlowRun.state_type,
                        db.FlowRun.parent_task_run_id,
                        db.FlowRun.deployment_id,
                    ),
                )
                .where(
                    or_(
                        db.FlowRun.state_type == states.StateType.PENDING,
                        db.FlowRun.state_type == states.StateType.SCHEDULED,
                        db.FlowRun.state_type == states.StateType.RUNNING,
                        db.FlowRun.state_type == states.StateType.PAUSED,
                        db.FlowRun.state_type == states.StateType.CANCELLING,
                    ),
                    db.FlowRun.id > high_water_mark,
                    db.FlowRun.parent_task_run_id.is_not(None),
                )
                .order_by(db.FlowRun.id)
                .limit(self.batch_size)
            )

            async with db.session_context() as session:
                subflow_run_result = await session.execute(subflow_query)
            subflow_runs = subflow_run_result.scalars().all()

            for subflow_run in subflow_runs:
                await self._cancel_subflow(db=db, flow_run=subflow_run)
                high_water_mark = max(high_water_mark, subflow_run.id)

            # if no relevant flows were found, exit the loop
            if len(subflow_runs) < self.batch_size:
                break

    async def _cancel_child_runs(
        self, db: PrefectDBInterface, flow_run: orm_models.FlowRun
    ) -> None:
        async with db.session_context() as session:
            child_task_runs = await models.task_runs.read_task_runs(
                session,
                flow_run_filter=filters.FlowRunFilter(
                    id=filters.FlowRunFilterId(any_=[flow_run.id])
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
                    state=states.Cancelled(
                        message="The parent flow run was cancelled."
                    ),
                    force=True,
                )

    async def _cancel_subflow(
        self, db: PrefectDBInterface, flow_run: orm_models.FlowRun
    ) -> Optional[bool]:
        if not flow_run.parent_task_run_id or not flow_run.state:
            return False

        if flow_run.state.type in states.TERMINAL_STATES:
            return False

        async with db.session_context() as session:
            parent_task_run = await models.task_runs.read_task_run(
                session, task_run_id=flow_run.parent_task_run_id
            )

            if not parent_task_run or not parent_task_run.flow_run_id:
                # Global orchestration policy will prevent further orchestration
                return False

            containing_flow_run = await models.flow_runs.read_flow_run(
                session, flow_run_id=parent_task_run.flow_run_id
            )

            if (
                containing_flow_run
                and containing_flow_run.state
                and containing_flow_run.state.type != states.StateType.CANCELLED
            ):
                # Nothing to do here; the parent is not cancelled
                return False

            if flow_run.deployment_id:
                state = states.Cancelling(message="The parent flow run was cancelled.")
            else:
                state = states.Cancelled(message="The parent flow run was cancelled.")

        async with db.session_context(begin_transaction=True) as session:
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=state,
            )


if __name__ == "__main__":
    asyncio.run(CancellationCleanup(handle_signals=True).start())
