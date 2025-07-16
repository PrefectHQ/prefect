"""
Routes for interacting with task run objects.
"""

import asyncio
import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path,
    Response,
    WebSocket,
    status,
)
from fastapi.responses import ORJSONResponse
from starlette.websockets import WebSocketDisconnect

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.api.run_history import run_history
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.orchestration import dependencies as orchestration_dependencies
from prefect.server.orchestration.core_policy import CoreTaskPolicy
from prefect.server.orchestration.policies import TaskRunOrchestrationPolicy
from prefect.server.schemas.responses import (
    OrchestrationResult,
    TaskRunPaginationResponse,
)
from prefect.server.task_queue import MultiQueue, TaskQueue
from prefect.server.utilities import subscriptions
from prefect.server.utilities.server import PrefectRouter
from prefect.types import DateTime
from prefect.types._datetime import now

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger("server.api")

router: PrefectRouter = PrefectRouter(prefix="/task_runs", tags=["Task Runs"])


@router.post("/")
async def create_task_run(
    task_run: schemas.actions.TaskRunCreate,
    response: Response,
    db: PrefectDBInterface = Depends(provide_database_interface),
    orchestration_parameters: Dict[str, Any] = Depends(
        orchestration_dependencies.provide_task_orchestration_parameters
    ),
) -> schemas.core.TaskRun:
    """
    Create a task run. If a task run with the same flow_run_id,
    task_key, and dynamic_key already exists, the existing task
    run will be returned.

    If no state is provided, the task run will be created in a PENDING state.

    For more information, see https://docs.prefect.io/v3/develop/write-tasks.
    """
    # hydrate the input model into a full task run / state model
    task_run_dict = task_run.model_dump()
    if not task_run_dict.get("id"):
        task_run_dict.pop("id", None)
    task_run = schemas.core.TaskRun(**task_run_dict)

    if not task_run.state:
        task_run.state = schemas.states.Pending()

    right_now = now("UTC")

    async with db.session_context(begin_transaction=True) as session:
        model = await models.task_runs.create_task_run(
            session=session,
            task_run=task_run,
            orchestration_parameters=orchestration_parameters,
        )

    if model.created >= right_now:
        response.status_code = status.HTTP_201_CREATED

    new_task_run: schemas.core.TaskRun = schemas.core.TaskRun.model_validate(model)

    return new_task_run


@router.patch("/{id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def update_task_run(
    task_run: schemas.actions.TaskRunUpdate,
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Updates a task run.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.task_runs.update_task_run(
            session=session, task_run=task_run, task_run_id=task_run_id
        )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task run not found")


@router.post("/count")
async def count_task_runs(
    db: PrefectDBInterface = Depends(provide_database_interface),
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
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[schemas.responses.HistoryResponse]:
    """
    Query for task run history data across a given range and interval.
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
            run_type="task_run",
            history_start=history_start,
            history_end=history_end,
            history_interval=history_interval,
            flows=flows,
            flow_runs=flow_runs,
            task_runs=task_runs,
            deployments=deployments,
        )


@router.get("/{id:uuid}")
async def read_task_run(
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
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
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
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


@router.post("/paginate", response_class=ORJSONResponse)
async def paginate_task_runs(
    sort: schemas.sorting.TaskRunSort = Body(schemas.sorting.TaskRunSort.ID_DESC),
    limit: int = dependencies.LimitBody(),
    page: int = Body(1, ge=1),
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> TaskRunPaginationResponse:
    """
    Pagination query for task runs.
    """
    offset = (page - 1) * limit

    async with db.session_context() as session:
        runs = await models.task_runs.read_task_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            offset=offset,
            limit=limit,
            sort=sort,
        )

        total_count = await models.task_runs.count_task_runs(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
        )

        return TaskRunPaginationResponse.model_validate(
            dict(
                results=runs,
                count=total_count,
                limit=limit,
                pages=(total_count + limit - 1) // limit,
                page=page,
            )
        )


@router.delete("/{id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_run(
    background_tasks: BackgroundTasks,
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """
    Delete a task run by id.
    """
    async with db.session_context(begin_transaction=True) as session:
        result = await models.task_runs.delete_task_run(
            session=session, task_run_id=task_run_id
        )
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    background_tasks.add_task(delete_task_run_logs, db, task_run_id)


async def delete_task_run_logs(db: PrefectDBInterface, task_run_id: UUID) -> None:
    async with db.session_context(begin_transaction=True) as session:
        await models.logs.delete_logs(
            session=session,
            log_filter=schemas.filters.LogFilter(
                task_run_id=schemas.filters.LogFilterTaskRunId(any_=[task_run_id])
            ),
        )


@router.post("/{id:uuid}/set_state")
async def set_task_run_state(
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
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
    task_policy: TaskRunOrchestrationPolicy = Depends(
        orchestration_dependencies.provide_task_policy
    ),
    orchestration_parameters: Dict[str, Any] = Depends(
        orchestration_dependencies.provide_task_orchestration_parameters
    ),
) -> OrchestrationResult:
    """Set a task run state, invoking any orchestration rules."""

    right_now = now("UTC")

    # create the state
    async with db.session_context(
        begin_transaction=True, with_for_update=True
    ) as session:
        orchestration_result = await models.task_runs.set_task_run_state(
            session=session,
            task_run_id=task_run_id,
            state=schemas.states.State.model_validate(
                state
            ),  # convert to a full State object
            force=force,
            task_policy=CoreTaskPolicy,
            orchestration_parameters=orchestration_parameters,
        )

    # set the 201 if a new state was created
    if orchestration_result.state and orchestration_result.state.timestamp >= right_now:
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return orchestration_result


@router.websocket("/subscriptions/scheduled")
async def scheduled_task_subscription(websocket: WebSocket) -> None:
    websocket = await subscriptions.accept_prefect_socket(websocket)
    if not websocket:
        return

    try:
        subscription = await websocket.receive_json()
    except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:
        return

    if subscription.get("type") != "subscribe":
        return await websocket.close(
            code=4001, reason="Protocol violation: expected 'subscribe' message"
        )

    task_keys = subscription.get("keys", [])
    if not task_keys:
        return await websocket.close(
            code=4001, reason="Protocol violation: expected 'keys' in subscribe message"
        )

    if not (client_id := subscription.get("client_id")):
        return await websocket.close(
            code=4001,
            reason="Protocol violation: expected 'client_id' in subscribe message",
        )

    subscribed_queue = MultiQueue(task_keys)

    logger.info(f"Task worker {client_id!r} subscribed to task keys {task_keys!r}")

    while True:
        try:
            # observe here so that all workers with active websockets are tracked
            await models.task_workers.observe_worker(task_keys, client_id)
            task_run = await asyncio.wait_for(subscribed_queue.get(), timeout=1)
        except asyncio.TimeoutError:
            if not await subscriptions.still_connected(websocket):
                await models.task_workers.forget_worker(client_id)
                return
            continue

        try:
            await websocket.send_json(task_run.model_dump(mode="json"))

            acknowledgement = await websocket.receive_json()
            ack_type = acknowledgement.get("type")
            if ack_type != "ack":
                if ack_type == "quit":
                    return await websocket.close()

                raise WebSocketDisconnect(
                    code=4001, reason="Protocol violation: expected 'ack' message"
                )

            await models.task_workers.observe_worker([task_run.task_key], client_id)

        except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:
            # If sending fails or pong fails, put the task back into the retry queue
            await asyncio.shield(TaskQueue.for_key(task_run.task_key).retry(task_run))
            return
        finally:
            await models.task_workers.forget_worker(client_id)
