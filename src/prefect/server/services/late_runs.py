"""
The MarkLateRuns service. Responsible for putting flow runs in a Late state if they are not started on time.
The threshold for a late run can be configured by changing `PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS`.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.models as models
from prefect.server.database import PrefectDBInterface, inject_db
from prefect.server.database.dependencies import db_injector
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.orchestration.core_policy import MarkLateRunsPolicy
from prefect.server.schemas import states
from prefect.server.services.base import LoopService
from prefect.settings import (
    PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS,
    PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS,
)
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import DateTime, now

if TYPE_CHECKING:
    from uuid import UUID


class MarkLateRuns(LoopService):
    """
    Finds flow runs that are later than their scheduled start time

    A flow run is defined as "late" if has not scheduled within a certain amount
    of time after its scheduled start time. The exact amount is configurable in
    Prefect REST API Settings.
    """

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.late_runs

    def __init__(self, loop_seconds: float | None = None, **kwargs: Any):
        super().__init__(
            loop_seconds=loop_seconds
            or PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS.value(),
            **kwargs,
        )

        # mark runs late if they are this far past their expected start time
        self.mark_late_after: datetime.timedelta = (
            PREFECT_API_SERVICES_LATE_RUNS_AFTER_SECONDS.value()
        )

        # query for this many runs to mark as late at once
        self.batch_size = 400

    @db_injector
    async def run_once(self, db: PrefectDBInterface) -> None:
        """
        Mark flow runs as late by:

        - Querying for flow runs in a scheduled state that are Scheduled to start in the past
        - For any runs past the "late" threshold, setting the flow run state to a new `Late` state
        """
        scheduled_to_start_before = now("UTC") - datetime.timedelta(
            seconds=self.mark_late_after.total_seconds()
        )

        while True:
            async with db.session_context(begin_transaction=True) as session:
                query = self._get_select_late_flow_runs_query(
                    scheduled_to_start_before=scheduled_to_start_before, db=db
                )

                result = await session.execute(query)
                runs = result.all()

                # mark each run as late
                for run in runs:
                    await self._mark_flow_run_as_late(session=session, flow_run=run)

                # if no runs were found, exit the loop
                if len(runs) < self.batch_size:
                    break

        self.logger.info("Finished monitoring for late runs.")

    @inject_db
    def _get_select_late_flow_runs_query(
        self, scheduled_to_start_before: datetime.datetime, db: PrefectDBInterface
    ) -> sa.Select[tuple["UUID", DateTime | None]]:
        """
        Returns a sqlalchemy query for late flow runs.

        Args:
            scheduled_to_start_before: the maximum next scheduled start time of
                scheduled flow runs to consider in the returned query
        """
        query = (
            sa.select(
                db.FlowRun.id,
                db.FlowRun.next_scheduled_start_time,
            )
            .where(
                # The next scheduled start time is in the past, including the mark late
                # after buffer
                (db.FlowRun.next_scheduled_start_time <= scheduled_to_start_before),
                db.FlowRun.state_type == states.StateType.SCHEDULED,
                db.FlowRun.state_name == "Scheduled",
            )
            .limit(self.batch_size)
        )
        return query

    async def _mark_flow_run_as_late(
        self,
        session: AsyncSession,
        flow_run: sa.Row[tuple["UUID", DateTime | None]],
    ) -> None:
        """
        Mark a flow run as late.

        Pass-through method for overrides.
        """
        try:
            await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run.id,
                state=states.Late(scheduled_time=flow_run.next_scheduled_start_time),
                flow_policy=MarkLateRunsPolicy,  # type: ignore
            )
        except ObjectNotFoundError:
            return  # flow run was deleted, ignore it


if __name__ == "__main__":
    asyncio.run(MarkLateRuns(handle_signals=True).start())
