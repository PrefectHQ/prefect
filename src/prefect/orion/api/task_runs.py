"""
Routes for interacting with task run objects.
"""

import datetime
from typing import List
from uuid import UUID

import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.orion.api.run_history import run_history
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.orchestration import dependencies as orchestration_dependencies
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.schemas.responses import OrchestrationResult
from prefect.orion.utilities.schemas import DateTimeTZ
from prefect.orion.utilities.server import OrionRouter

router = OrionRouter(prefix="/task_runs", tags=["Task Runs"])


@router.post("/")
async def create_task_run(
    task_run: schemas.actions.TaskRunCreate,
    response: Response,
    db: OrionDBInterface = Depends(provide_database_interface),
    orchestration_parameters: dict = Depends(
        orchestration_dependencies.provide_task_orchestration_parameters
    ),
) -> schemas.core.TaskRun:
    """
    Create a task run. If a task run with the same flow_run_id,
    task_key, and dynamic_key already exists, the existing task
    run will be returned.

    If no state is provided, the task run will be created in a PENDING state.
    """
    # hydrate the input model into a full task run / state model
    task_run = schemas.core.TaskRun(**task_run.dict())

    if not task_run.state:
        task_run.state = schemas.states.Pending()

    now = pendulum.now("UTC")

    async with db.session_context(begin_transaction=True) as session:
        model = await models.task_runs.create_task_run(
            session=session,
            task_run=task_run,
            orchestration_parameters=orchestration_parameters,
        )

    if model.created >= now:
        response.status_code = status.HTTP_201_CREATED
    return model


@router.post("/count")
async def count_task_runs(
    db: OrionDBInterface = Depends(provide_database_interface),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
) -> int:
    """
    Count task runs.
    """
    async with db.session_context() as session:
        return await models.task_runs.count_task_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
        )


@router.post("/history")
async def task_run_history(
    history_start: DateTimeTZ = Body(..., description="The history's start time."),
    history_end: DateTimeTZ = Body(..., description="The history's end time."),
    history_interval: datetime.timedelta = Body(
        ...,
        description="The size of each history interval, in seconds. Must be at least 1 second.",
        alias="history_interval_seconds",
    ),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.HistoryResponse]:
    """
    Query for task run history data across a given range and interval.
    """
    if history_interval < datetime.timedelta(seconds=1):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="History interval must not be less than 1 second.",
        )

    async with db.session_context() as session:
        return await run_history(
            session=session,
            run_type="task_run",
            history_start=history_start,
            history_end=history_end,
            history_interval=history_interval,
            flows=flows,
            flow_runs=flow_runs,
            task_runs=task_runs,
            deployments=deployments,
        )


@router.get("/{id}")
async def read_task_run(
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.core.TaskRun:
    """
    Get a task run by id.
    """
    async with db.session_context() as session:
        task_run = await models.task_runs.read_task_run(
            session=session, task_run_id=task_run_id
        )
    if not task_run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task_run


@router.post("/filter")
async def read_task_runs(
    sort: schemas.sorting.TaskRunSort = Body(schemas.sorting.TaskRunSort.ID_DESC),
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.TaskRun]:
    """
    Query for task runs.
    """
    async with db.session_context() as session:
        return await models.task_runs.read_task_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            offset=offset,
            limit=limit,
            sort=sort,
        )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_run(
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a task run by id.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.task_runs.delete_task_run(
            session=session, task_run_id=task_run_id
        )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")


@router.post("/{id}/set_state")
async def set_task_run_state(
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    state: schemas.actions.StateCreate = Body(..., description="The intended state."),
    force: bool = Body(
        False,
        description=(
            "If false, orchestration rules will be applied that may alter "
            "or prevent the state transition. If True, orchestration rules are not applied."
        ),
    ),
    db: OrionDBInterface = Depends(provide_database_interface),
    response: Response = None,
    task_policy: BaseOrchestrationPolicy = Depends(
        orchestration_dependencies.provide_task_policy
    ),
    orchestration_parameters: dict = Depends(
        orchestration_dependencies.provide_task_orchestration_parameters
    ),
) -> OrchestrationResult:
    """Set a task run state, invoking any orchestration rules."""

    # create the state
    async with db.session_context(begin_transaction=True) as session:
        orchestration_result = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run_id,
            state=schemas.states.State.parse_obj(
                state
            ),  # convert to a full State object
            force=force,
            task_policy=task_policy,
            orchestration_parameters=orchestration_parameters,
        )

    if orchestration_result.status == schemas.responses.SetStateStatus.WAIT:
        response.status_code = status.HTTP_200_OK
    elif orchestration_result.status == schemas.responses.SetStateStatus.ABORT:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_201_CREATED

    return orchestration_result
