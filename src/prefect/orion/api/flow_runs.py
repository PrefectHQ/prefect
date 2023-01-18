"""
Routes for interacting with flow run objects.
"""

import datetime
from typing import List
from uuid import UUID

import pendulum
from fastapi import Body, Depends, HTTPException, Path, Response, status
from fastapi.responses import ORJSONResponse

import prefect.orion.api.dependencies as dependencies
import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.logging import get_logger
from prefect.orion.api.run_history import run_history
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.models.flow_runs import DependencyResult
from prefect.orion.orchestration import dependencies as orchestration_dependencies
from prefect.orion.orchestration.policies import BaseOrchestrationPolicy
from prefect.orion.schemas.responses import OrchestrationResult
from prefect.orion.utilities.schemas import DateTimeTZ
from prefect.orion.utilities.server import OrionRouter

logger = get_logger("orion.api")

router = OrionRouter(prefix="/flow_runs", tags=["Flow Runs"])


@router.post("/")
async def create_flow_run(
    flow_run: schemas.actions.FlowRunCreate,
    db: OrionDBInterface = Depends(provide_database_interface),
    response: Response = None,
    orchestration_parameters: dict = Depends(
        orchestration_dependencies.provide_flow_orchestration_parameters
    ),
    api_version=Depends(dependencies.provide_request_api_version),
) -> schemas.responses.FlowRunResponse:
    """
    Create a flow run. If a flow run with the same flow_id and
    idempotency key already exists, the existing flow run will be returned.

    If no state is provided, the flow run will be created in a PENDING state.
    """
    # hydrate the input model into a full flow run / state model
    flow_run = schemas.core.FlowRun(**flow_run.dict())

    # pass the request version to the orchestration engine to support compatibility code
    orchestration_parameters.update({"api-version": api_version})

    if not flow_run.state:
        flow_run.state = schemas.states.Pending()

    now = pendulum.now("UTC")

    async with db.session_context(begin_transaction=True) as session:
        model = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=flow_run,
            orchestration_parameters=orchestration_parameters,
        )
        if model.created >= now:
            response.status_code = status.HTTP_201_CREATED

        return schemas.responses.FlowRunResponse.from_orm(model)


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_flow_run(
    flow_run: schemas.actions.FlowRunUpdate,
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Updates a flow run.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.flow_runs.update_flow_run(
            session=session, flow_run=flow_run, flow_run_id=flow_run_id
        )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Flow run not found")


@router.post("/count")
async def count_flow_runs(
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    work_pool_queues: schemas.filters.WorkPoolQueueFilter = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> int:
    """
    Query for flow runs.
    """
    async with db.session_context() as session:
        return await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            work_pool_queue_filter=work_pool_queues,
        )


@router.post("/history")
async def flow_run_history(
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
    Query for flow run history data across a given range and interval.
    """
    if history_interval < datetime.timedelta(seconds=1):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="History interval must not be less than 1 second.",
        )

    async with db.session_context() as session:
        return await run_history(
            session=session,
            run_type="flow_run",
            history_start=history_start,
            history_end=history_end,
            history_interval=history_interval,
            flows=flows,
            flow_runs=flow_runs,
            task_runs=task_runs,
            deployments=deployments,
        )


@router.get("/{id}")
async def read_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> schemas.responses.FlowRunResponse:
    """
    Get a flow run by id.
    """
    async with db.session_context() as session:
        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )
        if not flow_run:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Flow run not found")
        return schemas.responses.FlowRunResponse.from_orm(flow_run)


@router.get("/{id}/graph")
async def read_flow_run_graph(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[DependencyResult]:
    """
    Get a task run dependency map for a given flow run.
    """
    async with db.session_context() as session:
        return await models.flow_runs.read_task_run_dependencies(
            session=session, flow_run_id=flow_run_id
        )


@router.post("/{id}/resume")
async def resume_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
    response: Response = None,
    flow_policy: BaseOrchestrationPolicy = Depends(
        orchestration_dependencies.provide_flow_policy
    ),
    orchestration_parameters: dict = Depends(
        orchestration_dependencies.provide_flow_orchestration_parameters
    ),
    api_version=Depends(dependencies.provide_request_api_version),
) -> OrchestrationResult:
    """
    Resume a paused flow run.
    """
    now = pendulum.now()

    async with db.session_context(begin_transaction=True) as session:
        flow_run = await models.flow_runs.read_flow_run(session, flow_run_id)
        state = flow_run.state

        if state is None or state.type != schemas.states.StateType.PAUSED:
            result = OrchestrationResult(
                state=None,
                status=schemas.responses.SetStateStatus.ABORT,
                details=schemas.responses.StateAbortDetails(
                    reason="Cannot resume a flow run that is not paused."
                ),
            )
            return result

        orchestration_parameters.update({"api-version": api_version})

        if state.state_details.pause_reschedule:
            orchestration_result = await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run_id,
                state=schemas.states.Scheduled(
                    name="Resuming", scheduled_time=pendulum.now("UTC")
                ),
                flow_policy=flow_policy,
                orchestration_parameters=orchestration_parameters,
            )
        else:
            orchestration_result = await models.flow_runs.set_flow_run_state(
                session=session,
                flow_run_id=flow_run_id,
                state=schemas.states.Running(),
                flow_policy=flow_policy,
                orchestration_parameters=orchestration_parameters,
            )

        # set the 201 if a new state was created
        if orchestration_result.state and orchestration_result.state.timestamp >= now:
            response.status_code = status.HTTP_201_CREATED
        else:
            response.status_code = status.HTTP_200_OK

        return orchestration_result


@router.post("/filter", response_class=ORJSONResponse)
async def read_flow_runs(
    sort: schemas.sorting.FlowRunSort = Body(schemas.sorting.FlowRunSort.ID_DESC),
    limit: int = dependencies.LimitBody(),
    offset: int = Body(0, ge=0),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    work_pool_queues: schemas.filters.WorkPoolQueueFilter = None,
    db: OrionDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.FlowRunResponse]:
    """
    Query for flow runs.
    """
    async with db.session_context() as session:
        db_flow_runs = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            work_pool_queue_filter=work_pool_queues,
            offset=offset,
            limit=limit,
            sort=sort,
        )

        # Instead of relying on fastapi.encoders.jsonable_encoder to convert the
        # response to JSON, we do so more efficiently ourselves.
        # In particular, the FastAPI encoder is very slow for large, nested objects.
        # See: https://github.com/tiangolo/fastapi/issues/1224
        encoded = [
            schemas.responses.FlowRunResponse.from_orm(fr).dict(json_compatible=True)
            for fr in db_flow_runs
        ]
        return ORJSONResponse(content=encoded)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: OrionDBInterface = Depends(provide_database_interface),
):
    """
    Delete a flow run by id.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.flow_runs.delete_flow_run(
            session=session, flow_run_id=flow_run_id
        )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow run not found"
        )


@router.post("/{id}/set_state")
async def set_flow_run_state(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
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
    flow_policy: BaseOrchestrationPolicy = Depends(
        orchestration_dependencies.provide_flow_policy
    ),
    orchestration_parameters: dict = Depends(
        orchestration_dependencies.provide_flow_orchestration_parameters
    ),
    api_version=Depends(dependencies.provide_request_api_version),
) -> OrchestrationResult:
    """Set a flow run state, invoking any orchestration rules."""

    # pass the request version to the orchestration engine to support compatibility code
    orchestration_parameters.update({"api-version": api_version})

    now = pendulum.now()

    # create the state
    async with db.session_context(begin_transaction=True) as session:
        orchestration_result = await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_id,
            # convert to a full State object
            state=schemas.states.State.parse_obj(state),
            force=force,
            flow_policy=flow_policy,
            orchestration_parameters=orchestration_parameters,
        )

    # set the 201 if a new state was created
    if orchestration_result.state and orchestration_result.state.timestamp >= now:
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return orchestration_result
