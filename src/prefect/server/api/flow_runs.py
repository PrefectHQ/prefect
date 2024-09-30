"""
Routes for interacting with flow run objects.
"""

import csv
import datetime
import io
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

import orjson
import pendulum
import sqlalchemy as sa
from fastapi import (
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from fastapi.responses import ORJSONResponse, PlainTextResponse, StreamingResponse
from pydantic_extra_types.pendulum_dt import DateTime
from sqlalchemy.exc import IntegrityError

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.api.run_history import run_history
from prefect.server.api.validation import validate_job_variables_for_deployment_flow_run
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.exceptions import FlowRunGraphTooLarge
from prefect.server.models.flow_runs import (
    DependencyResult,
    read_flow_run_graph,
)
from prefect.server.orchestration import dependencies as orchestration_dependencies
from prefect.server.orchestration.policies import BaseOrchestrationPolicy
from prefect.server.schemas.graph import Graph
from prefect.server.schemas.responses import (
    FlowRunPaginationResponse,
    OrchestrationResult,
)
from prefect.server.utilities.server import PrefectRouter
from prefect.utilities import schema_tools

logger = get_logger("server.api")

router = PrefectRouter(prefix="/flow_runs", tags=["Flow Runs"])


@router.post("/")
async def create_flow_run(
    flow_run: schemas.actions.FlowRunCreate,
    db: PrefectDBInterface = Depends(provide_database_interface),
    response: Response = None,
    created_by: Optional[schemas.core.CreatedBy] = Depends(dependencies.get_created_by),
    orchestration_parameters: Dict[str, Any] = Depends(
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
    flow_run = schemas.core.FlowRun(**flow_run.model_dump(), created_by=created_by)

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

        return schemas.responses.FlowRunResponse.model_validate(
            model, from_attributes=True
        )


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_flow_run(
    flow_run: schemas.actions.FlowRunUpdate,
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """
    Updates a flow run.
    """
    async with db.session_context(begin_transaction=True) as session:
        if flow_run.job_variables is not None:
            this_run = await models.flow_runs.read_flow_run(
                session, flow_run_id=flow_run_id
            )
            if this_run is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Flow run not found"
                )
            if not this_run.state:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Flow run state is required to update job variables but none exists",
                )
            if this_run.state.type != schemas.states.StateType.SCHEDULED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Job variables for a flow run in state {this_run.state.type.name} cannot be updated",
                )
            if this_run.deployment_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A deployment for the flow run could not be found",
                )

            deployment = await models.deployments.read_deployment(
                session=session, deployment_id=this_run.deployment_id
            )
            if deployment is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A deployment for the flow run could not be found",
                )

            await validate_job_variables_for_deployment_flow_run(
                session, deployment, flow_run
            )

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
    work_pool_queues: schemas.filters.WorkQueueFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
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
            work_queue_filter=work_pool_queues,
        )


@router.post("/lateness")
async def average_flow_run_lateness(
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    work_pools: Optional[schemas.filters.WorkPoolFilter] = None,
    work_pool_queues: Optional[schemas.filters.WorkQueueFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Optional[float]:
    """
    Query for average flow-run lateness in seconds.
    """
    async with db.session_context() as session:
        if db.dialect.name == "sqlite":
            # Since we want an _average_ of the lateness we're unable to use
            # the existing FlowRun.expected_start_time_delta property as it
            # returns a timedelta and SQLite is unable to properly deal with it
            # and always returns 1970.0 as the average. This copies the same
            # logic but ensures that it returns the number of seconds instead
            # so it's compatible with SQLite.
            base_query = sa.case(
                (
                    db.FlowRun.start_time > db.FlowRun.expected_start_time,
                    sa.func.strftime("%s", db.FlowRun.start_time)
                    - sa.func.strftime("%s", db.FlowRun.expected_start_time),
                ),
                (
                    db.FlowRun.start_time.is_(None)
                    & db.FlowRun.state_type.notin_(schemas.states.TERMINAL_STATES)
                    & (db.FlowRun.expected_start_time < sa.func.datetime("now")),
                    sa.func.strftime("%s", sa.func.datetime("now"))
                    - sa.func.strftime("%s", db.FlowRun.expected_start_time),
                ),
                else_=0,
            )
        else:
            base_query = db.FlowRun.estimated_start_time_delta

        query = await models.flow_runs._apply_flow_run_filters(
            sa.select(sa.func.avg(base_query)),
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            work_queue_filter=work_pool_queues,
        )
        result = await session.execute(query)

        avg_lateness = result.scalar()

        if avg_lateness is None:
            return None
        elif isinstance(avg_lateness, datetime.timedelta):
            return avg_lateness.total_seconds()
        else:
            return avg_lateness


@router.post("/history")
async def flow_run_history(
    history_start: DateTime = Body(..., description="The history's start time."),
    history_end: DateTime = Body(..., description="The history's end time."),
    # Workaround for the fact that FastAPI does not let us configure ser_json_timedelta
    # to represent timedeltas as floats in JSON.
    history_interval: float = Body(
        ...,
        description=(
            "The size of each history interval, in seconds. Must be at least 1 second."
        ),
        json_schema_extra={"format": "time-delta"},
        alias="history_interval_seconds",
    ),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    work_pools: schemas.filters.WorkPoolFilter = None,
    work_queues: schemas.filters.WorkQueueFilter = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.HistoryResponse]:
    """
    Query for flow run history data across a given range and interval.
    """
    if isinstance(history_interval, float):
        history_interval = datetime.timedelta(seconds=history_interval)

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
            work_pools=work_pools,
            work_queues=work_queues,
        )


@router.get("/{id}")
async def read_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
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
        return schemas.responses.FlowRunResponse.model_validate(
            flow_run, from_attributes=True
        )


@router.get("/{id}/graph")
async def read_flow_run_graph_v1(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[DependencyResult]:
    """
    Get a task run dependency map for a given flow run.
    """
    async with db.session_context() as session:
        return await models.flow_runs.read_task_run_dependencies(
            session=session, flow_run_id=flow_run_id
        )


@router.get("/{id:uuid}/graph-v2")
async def read_flow_run_graph_v2(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    since: datetime.datetime = Query(
        datetime.datetime.min,
        description="Only include runs that start or end after this time.",
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Graph:
    """
    Get a graph of the tasks and subflow runs for the given flow run
    """
    async with db.session_context() as session:
        try:
            return await read_flow_run_graph(
                session=session,
                flow_run_id=flow_run_id,
                since=since,
            )
        except FlowRunGraphTooLarge as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )


@router.post("/{id}/resume")
async def resume_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
    run_input: Optional[Dict] = Body(default=None, embed=True),
    response: Response = None,
    flow_policy: Type[BaseOrchestrationPolicy] = Depends(
        orchestration_dependencies.provide_flow_policy
    ),
    task_policy: BaseOrchestrationPolicy = Depends(
        orchestration_dependencies.provide_task_policy
    ),
    orchestration_parameters: Dict[str, Any] = Depends(
        orchestration_dependencies.provide_flow_orchestration_parameters
    ),
    api_version=Depends(dependencies.provide_request_api_version),
) -> OrchestrationResult:
    """
    Resume a paused flow run.
    """
    now = pendulum.now("UTC")

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

        keyset = state.state_details.run_input_keyset

        if keyset:
            run_input = run_input or {}

            try:
                hydration_context = await schema_tools.HydrationContext.build(
                    session=session,
                    raise_on_error=True,
                    render_jinja=True,
                    render_workspace_variables=True,
                )
                run_input = schema_tools.hydrate(run_input, hydration_context) or {}
            except schema_tools.HydrationError as exc:
                return OrchestrationResult(
                    state=state,
                    status=schemas.responses.SetStateStatus.REJECT,
                    details=schemas.responses.StateAbortDetails(
                        reason=f"Error hydrating run input: {exc}",
                    ),
                )

            schema_json = await models.flow_run_input.read_flow_run_input(
                session=session, flow_run_id=flow_run.id, key=keyset["schema"]
            )

            if schema_json is None:
                return OrchestrationResult(
                    state=state,
                    status=schemas.responses.SetStateStatus.REJECT,
                    details=schemas.responses.StateAbortDetails(
                        reason="Run input schema not found."
                    ),
                )

            try:
                schema = orjson.loads(schema_json.value)
            except orjson.JSONDecodeError:
                return OrchestrationResult(
                    state=state,
                    status=schemas.responses.SetStateStatus.REJECT,
                    details=schemas.responses.StateAbortDetails(
                        reason="Run input schema is not valid JSON."
                    ),
                )

            try:
                schema_tools.validate(run_input, schema, raise_on_error=True)
            except schema_tools.ValidationError as exc:
                return OrchestrationResult(
                    state=state,
                    status=schemas.responses.SetStateStatus.REJECT,
                    details=schemas.responses.StateAbortDetails(
                        reason=f"Reason: {exc}"
                    ),
                )
            except schema_tools.CircularSchemaRefError:
                return OrchestrationResult(
                    state=state,
                    status=schemas.responses.SetStateStatus.REJECT,
                    details=schemas.responses.StateAbortDetails(
                        reason="Invalid schema: Unable to validate schema with circular references.",
                    ),
                )

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

        if (
            keyset
            and run_input
            and orchestration_result.status == schemas.responses.SetStateStatus.ACCEPT
        ):
            # The state change is accepted, go ahead and store the validated
            # run input.
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.core.FlowRunInput(
                    flow_run_id=flow_run_id,
                    key=keyset["response"],
                    value=orjson.dumps(run_input).decode("utf-8"),
                ),
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
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    work_pools: Optional[schemas.filters.WorkPoolFilter] = None,
    work_pool_queues: Optional[schemas.filters.WorkQueueFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
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
            work_queue_filter=work_pool_queues,
            offset=offset,
            limit=limit,
            sort=sort,
        )

        # Instead of relying on fastapi.encoders.jsonable_encoder to convert the
        # response to JSON, we do so more efficiently ourselves.
        # In particular, the FastAPI encoder is very slow for large, nested objects.
        # See: https://github.com/tiangolo/fastapi/issues/1224
        encoded = [
            schemas.responses.FlowRunResponse.model_validate(
                fr, from_attributes=True
            ).model_dump(mode="json")
            for fr in db_flow_runs
        ]
        return ORJSONResponse(content=encoded)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_run(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
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
            "If false, orchestration rules will be applied that may alter or prevent"
            " the state transition. If True, orchestration rules are not applied."
        ),
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
    response: Response = None,
    flow_policy: Type[BaseOrchestrationPolicy] = Depends(
        orchestration_dependencies.provide_flow_policy
    ),
    orchestration_parameters: Dict[str, Any] = Depends(
        orchestration_dependencies.provide_flow_orchestration_parameters
    ),
    api_version=Depends(dependencies.provide_request_api_version),
) -> OrchestrationResult:
    """Set a flow run state, invoking any orchestration rules."""

    # pass the request version to the orchestration engine to support compatibility code
    orchestration_parameters.update({"api-version": api_version})

    now = pendulum.now("UTC")

    # create the state
    async with db.session_context(
        begin_transaction=True, with_for_update=True
    ) as session:
        orchestration_result = await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_id,
            # convert to a full State object
            state=schemas.states.State.model_validate(state),
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


@router.post("/{id}/input", status_code=status.HTTP_201_CREATED)
async def create_flow_run_input(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    key: str = Body(..., description="The input key"),
    value: bytes = Body(..., description="The value of the input"),
    sender: Optional[str] = Body(None, description="The sender of the input"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """
    Create a key/value input for a flow run.
    """
    async with db.session_context() as session:
        try:
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.core.FlowRunInput(
                    flow_run_id=flow_run_id,
                    key=key,
                    sender=sender,
                    value=value.decode(),
                ),
            )
            await session.commit()

        except IntegrityError as exc:
            if "unique constraint" in str(exc).lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A flow run input with this key already exists.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Flow run not found"
                )


@router.post("/{id}/input/filter")
async def filter_flow_run_input(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    prefix: str = Body(..., description="The input key prefix", embed=True),
    limit: int = Body(
        1, description="The maximum number of results to return", embed=True
    ),
    exclude_keys: List[str] = Body(
        [], description="Exclude inputs with these keys", embed=True
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.core.FlowRunInput]:
    """
    Filter flow run inputs by key prefix
    """
    async with db.session_context() as session:
        return await models.flow_run_input.filter_flow_run_input(
            session=session,
            flow_run_id=flow_run_id,
            prefix=prefix,
            limit=limit,
            exclude_keys=exclude_keys,
        )


@router.get("/{id}/input/{key}")
async def read_flow_run_input(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    key: str = Path(..., description="The input key", alias="key"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> PlainTextResponse:
    """
    Create a value from a flow run input
    """

    async with db.session_context() as session:
        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session, flow_run_id=flow_run_id, key=key
        )

    if flow_run_input:
        return PlainTextResponse(flow_run_input.value)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flow run input not found"
        )


@router.delete("/{id}/input/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow_run_input(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    key: str = Path(..., description="The input key", alias="key"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    """
    Delete a flow run input
    """

    async with db.session_context() as session:
        deleted = await models.flow_run_input.delete_flow_run_input(
            session=session, flow_run_id=flow_run_id, key=key
        )
        await session.commit()

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Flow run input not found"
            )


@router.post("/paginate", response_class=ORJSONResponse)
async def paginate_flow_runs(
    sort: schemas.sorting.FlowRunSort = Body(schemas.sorting.FlowRunSort.ID_DESC),
    limit: int = dependencies.LimitBody(),
    page: int = Body(1, ge=1),
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    work_pools: Optional[schemas.filters.WorkPoolFilter] = None,
    work_pool_queues: Optional[schemas.filters.WorkQueueFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> FlowRunPaginationResponse:
    """
    Pagination query for flow runs.
    """
    offset = (page - 1) * limit

    async with db.session_context() as session:
        runs = await models.flow_runs.read_flow_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            work_queue_filter=work_pool_queues,
            offset=offset,
            limit=limit,
            sort=sort,
        )

        count = await models.flow_runs.count_flow_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            work_pool_filter=work_pools,
            work_queue_filter=work_pool_queues,
        )

        # Instead of relying on fastapi.encoders.jsonable_encoder to convert the
        # response to JSON, we do so more efficiently ourselves.
        # In particular, the FastAPI encoder is very slow for large, nested objects.
        # See: https://github.com/tiangolo/fastapi/issues/1224
        results = [
            schemas.responses.FlowRunResponse.model_validate(
                run, from_attributes=True
            ).model_dump(mode="json")
            for run in runs
        ]

        response = FlowRunPaginationResponse(
            results=results,
            count=count,
            limit=limit,
            pages=(count + limit - 1) // limit,
            page=page,
        ).model_dump(mode="json")

        return ORJSONResponse(content=response)


FLOW_RUN_LOGS_DOWNLOAD_PAGE_LIMIT = 1000


@router.get("/{id}/logs/download")
async def download_logs(
    flow_run_id: UUID = Path(..., description="The flow run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> StreamingResponse:
    """
    Download all flow run logs as a CSV file, collecting all logs until there are no more logs to retrieve.
    """
    async with db.session_context() as session:
        flow_run = await models.flow_runs.read_flow_run(
            session=session, flow_run_id=flow_run_id
        )

        if not flow_run:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Flow run not found")

        async def generate():
            data = io.StringIO()
            csv_writer = csv.writer(data)
            csv_writer.writerow(
                ["timestamp", "level", "flow_run_id", "task_run_id", "message"]
            )

            offset = 0
            limit = FLOW_RUN_LOGS_DOWNLOAD_PAGE_LIMIT

            while True:
                results = await models.logs.read_logs(
                    session=session,
                    log_filter=schemas.filters.LogFilter(
                        flow_run_id={"any_": [flow_run_id]}
                    ),
                    offset=offset,
                    limit=limit,
                    sort=schemas.sorting.LogSort.TIMESTAMP_ASC,
                )

                if not results:
                    break

                offset += limit

                for log in results:
                    csv_writer.writerow(
                        [
                            log.timestamp,
                            log.level,
                            log.flow_run_id,
                            log.task_run_id,
                            log.message,
                        ]
                    )
                    data.seek(0)
                    yield data.read()
                    data.seek(0)
                    data.truncate(0)

        return StreamingResponse(
            generate(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={flow_run.name}-logs.csv"
            },
        )
