from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, List
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends
from pydantic import Field

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server import models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.server.utilities.server import PrefectRouter
from prefect.types import DateTime

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger("server.api.ui.flow_runs")

router: PrefectRouter = PrefectRouter(prefix="/ui/flow_runs", tags=["Flow Runs", "UI"])


class SimpleFlowRun(PrefectBaseModel):
    id: UUID = Field(default=..., description="The flow run id.")
    state_type: schemas.states.StateType = Field(
        default=..., description="The state type."
    )
    timestamp: DateTime = Field(
        default=...,
        description=(
            "The start time of the run, or the expected start time "
            "if it hasn't run yet."
        ),
    )
    duration: datetime.timedelta = Field(
        default=..., description="The total run time of the run."
    )
    lateness: datetime.timedelta = Field(
        default=..., description="The delay between the expected and actual start time."
    )


@router.post("/history")
async def read_flow_run_history(
    sort: schemas.sorting.FlowRunSort = Body(
        schemas.sorting.FlowRunSort.EXPECTED_START_TIME_DESC
    ),
    limit: int = Body(1000, le=1000),
    offset: int = Body(0, ge=0),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[SimpleFlowRun]:
    columns = [
        db.FlowRun.id,
        db.FlowRun.state_type,
        db.FlowRun.start_time,
        db.FlowRun.expected_start_time,
        db.FlowRun.total_run_time,
        # Although it isn't returned, we need to select
        # this field in order to compute `estimated_run_time`
        db.FlowRun.state_timestamp,
    ]
    async with db.session_context() as session:
        result = await models.flow_runs.read_flow_runs(
            columns=columns,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            sort=sort,
            limit=limit,
            offset=offset,
            session=session,
        )
    return [
        SimpleFlowRun(
            id=r.id,
            state_type=r.state_type,
            timestamp=r.start_time or r.expected_start_time,
            duration=r.estimated_run_time,
            lateness=r.estimated_start_time_delta,
        )
        for r in result
    ]


@router.post("/count-task-runs")
async def count_task_runs_by_flow_run(
    flow_run_ids: list[UUID] = Body(default=..., embed=True, max_items=200),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> dict[UUID, int]:
    """
    Get task run counts by flow run id.
    """
    async with db.session_context() as session:
        query = (
            sa.select(
                db.TaskRun.flow_run_id,
                sa.func.count(db.TaskRun.id).label("task_run_count"),
            )
            .where(
                sa.and_(
                    db.TaskRun.flow_run_id.in_(flow_run_ids),
                    sa.not_(db.TaskRun.subflow_run.has()),
                )
            )
            .group_by(db.TaskRun.flow_run_id)
        )

        results = await session.execute(query)

        task_run_counts_by_flow_run = {
            flow_run_id: task_run_count for flow_run_id, task_run_count in results.t
        }

        return {
            flow_run_id: task_run_counts_by_flow_run.get(flow_run_id, 0)
            for flow_run_id in flow_run_ids
        }
