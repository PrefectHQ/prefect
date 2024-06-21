"""
The TaskSchedulingTimeouts service reschedules background tasks that are stuck PENDING.
"""

import asyncio
from typing import Optional

import pendulum
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.api.task_runs import TaskQueue
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.orchestration import dependencies as orchestration_dependencies
from prefect.server.schemas import filters, states
from prefect.server.services.loop_service import LoopService
from prefect.settings import PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT


class TaskSchedulingTimeouts(LoopService):
    _first_run: bool

    def __init__(self, loop_seconds: Optional[float] = None, **kwargs):
        self._first_run = True
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT.value().total_seconds(),
            **kwargs,
        )

    @inject_db
    async def run_once(self, db: PrefectDBInterface):
        """
        Periodically reschedules pending task runs that have been pending for too long.
        """
        if not PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT:
            return

        async with db.session_context(begin_transaction=True) as session:
            if self._first_run:
                await self.restore_scheduled_tasks_if_necessary(session)
                self._first_run = False

            await self.reschedule_pending_runs(session)

    async def restore_scheduled_tasks_if_necessary(self, session: AsyncSession):
        """
        Restores scheduled task runs from the database to the in-memory queues.
        """
        task_runs = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=filters.TaskRunFilter(
                flow_run_id=filters.TaskRunFilterFlowRunId(is_null_=True),
                state=filters.TaskRunFilterState(
                    type=filters.TaskRunFilterStateType(
                        any_=[states.StateType.SCHEDULED]
                    )
                ),
            ),
        )

        for task_run_model in task_runs:
            task_run: schemas.core.TaskRun = schemas.core.TaskRun.model_validate(
                task_run_model
            )
            await TaskQueue.for_key(task_run.task_key).retry(task_run)

        self.logger.info("Restored %s scheduled task runs", len(task_runs))

    async def reschedule_pending_runs(self, session: AsyncSession):
        """
        Transitions any background task runs that have been PENDING too long into
        SCHEDULED, and reenqueues them.
        """
        task_runs = await models.task_runs.read_task_runs(
            session=session,
            task_run_filter=filters.TaskRunFilter(
                flow_run_id=filters.TaskRunFilterFlowRunId(is_null_=True),
                state=filters.TaskRunFilterState(
                    type=filters.TaskRunFilterStateType(any_=[states.StateType.PENDING])
                ),
            ),
        )

        older_than = (
            pendulum.now("UTC") - PREFECT_TASK_SCHEDULING_PENDING_TASK_TIMEOUT.value()
        )
        task_runs = [t for t in task_runs if t.state.timestamp <= older_than]

        orchestration_parameters = (
            await orchestration_dependencies.provide_task_orchestration_parameters()
        )
        for task_run in task_runs:
            self.logger.info("Rescheduling task run %s", task_run.id)
            previous_states = await models.task_run_states.read_task_run_states(
                session=session, task_run_id=task_run.id
            )
            previous_states.sort(key=lambda s: s.timestamp)
            for prior_scheduled_state in previous_states:
                if prior_scheduled_state.type == states.StateType.SCHEDULED:
                    break
            else:
                # This wasn't originally a SCHEDULED background task, so we won't
                # attempt to reschedule it.
                continue

            rescheduled = states.Scheduled(
                state_details={
                    "deferred": True,
                    "task_parameters_id": prior_scheduled_state.state_details.task_parameters_id,
                }
            )

            await models.task_runs.set_task_run_state(
                session=session,
                task_run_id=task_run.id,
                state=rescheduled,
                force=True,
                orchestration_parameters=orchestration_parameters,
            )

        self.logger.info("Rescheduled %s pending task runs", len(task_runs))


if __name__ == "__main__":
    asyncio.run(TaskSchedulingTimeouts().start())
