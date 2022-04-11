import datetime
from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import Body, Depends
from pydantic import Field

import prefect.orion.api.dependencies as dependencies
import prefect.orion.schemas as schemas
from prefect.logging import get_logger
from prefect.orion import models
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion.utilities.server import OrionRouter

logger = get_logger("orion.api.ui.flow_runs")

router = OrionRouter(prefix="/ui/flow_runs", tags=["Flow Runs", "UI"])


class SimpleFlowRun(PrefectBaseModel):
    id: UUID = Field(..., description="The flow run id.")
    state_type: schemas.states.StateType = Field(..., description="The state type.")
    timestamp: datetime.datetime = Field(
        ...,
        description="The start time of the run, or the expected start time "
        "if it hasn't run yet.",
    )
    duration: datetime.timedelta = Field(
        ..., description="The total run time of the run."
    )
    lateness: datetime.timedelta = Field(
        ..., description="The delay between the expected and actual start time."
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
    db: OrionDBInterface = Depends(dependencies.provide_database_interface),
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[SimpleFlowRun]:
    columns = [
        db.FlowRun.id,
        db.FlowRun.state_type,
        db.FlowRun.start_time,
        db.FlowRun.expected_start_time,
        db.FlowRun.total_run_time,
    ]
    result = await models.flow_runs.read_flow_runs(
        columns=columns,
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
        deployment_filter=deployments,
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
