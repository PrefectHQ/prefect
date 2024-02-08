"""
Routes for interacting with task run objects.
"""

import asyncio
import datetime
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import pendulum
from prefect._vendor.fastapi import (
    Body,
    Depends,
    HTTPException,
    Path,
    Response,
    WebSocket,
    status,
)
from typing_extensions import Self

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.api.run_history import run_history
from prefect.server.database.dependencies import inject_db, provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.orchestration import dependencies as orchestration_dependencies
from prefect.server.orchestration.policies import BaseOrchestrationPolicy
from prefect.server.schemas import filters, states
from prefect.server.schemas.responses import OrchestrationResult
from prefect.server.utilities import subscriptions
from prefect.server.utilities.schemas import DateTimeTZ
from prefect.server.utilities.server import PrefectRouter
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING,
    PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE,
    PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE,
)

logger = get_logger("server.api")


router = PrefectRouter(prefix="/task_runs", tags=["Task Runs"])


@router.post("/")
async def create_task_run(
    task_run: schemas.actions.TaskRunCreate,
    response: Response,
    db: PrefectDBInterface = Depends(provide_database_interface),
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

    new_task_run: schemas.core.TaskRun = schemas.core.TaskRun.from_orm(model)

    # Place autonomously scheduled task runs onto a notification queue for the websocket
    if (
        PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING.value()
        and new_task_run.flow_run_id is None
        and new_task_run.state
        and new_task_run.state.is_scheduled()
    ):
        await TaskQueue.enqueue(new_task_run)

    return new_task_run


@router.patch("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_task_run(
    task_run: schemas.actions.TaskRunUpdate,
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
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
    history_start: DateTimeTZ = Body(..., description="The history's start time."),
    history_end: DateTimeTZ = Body(..., description="The history's end time."),
    history_interval: datetime.timedelta = Body(
        ...,
        description=(
            "The size of each history interval, in seconds. Must be at least 1 second."
        ),
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
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
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


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_run(
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
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
            "If false, orchestration rules will be applied that may alter or prevent"
            " the state transition. If True, orchestration rules are not applied."
        ),
    ),
    db: PrefectDBInterface = Depends(provide_database_interface),
    response: Response = None,
    task_policy: BaseOrchestrationPolicy = Depends(
        orchestration_dependencies.provide_task_policy
    ),
    orchestration_parameters: dict = Depends(
        orchestration_dependencies.provide_task_orchestration_parameters
    ),
) -> OrchestrationResult:
    """Set a task run state, invoking any orchestration rules."""

    now = pendulum.now("UTC")

    # create the state
    async with db.session_context(
        begin_transaction=True, with_for_update=True
    ) as session:
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

    # set the 201 if a new state was created
    if orchestration_result.state and orchestration_result.state.timestamp >= now:
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return orchestration_result


class TaskQueue:
    _task_queues: Dict[str, Self] = {}
    _scheduled_tasks_already_restored: bool = False

    default_scheduled_max_size: int = (
        PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE.value()
    )
    default_retry_max_size: int = PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE.value()

    _queue_size_configs: Dict[str, Tuple[int, int]] = {}

    task_key: str
    _scheduled_queue: asyncio.Queue
    _retry_queue: asyncio.Queue

    @classmethod
    async def enqueue(cls, task_run: schemas.core.TaskRun) -> None:
        await cls.for_key(task_run.task_key).put(task_run)

    @classmethod
    def configure_task_key(
        cls,
        task_key: str,
        scheduled_size: Optional[int] = None,
        retry_size: Optional[int] = None,
    ):
        scheduled_size = scheduled_size or cls.default_scheduled_max_size
        retry_size = retry_size or cls.default_retry_max_size
        cls._queue_size_configs[task_key] = (scheduled_size, retry_size)

    @classmethod
    def for_key(cls, task_key: str) -> Self:
        if task_key not in cls._task_queues:
            sizes = cls._queue_size_configs.get(
                task_key, (cls.default_scheduled_max_size, cls.default_retry_max_size)
            )
            cls._task_queues[task_key] = cls(task_key, *sizes)
        return cls._task_queues[task_key]

    @classmethod
    def reset(cls) -> None:
        """A unit testing utility to reset the state of the task queues subsystem"""
        cls._task_queues.clear()
        cls._scheduled_tasks_already_restored = False

    def __init__(self, task_key: str, scheduled_queue_size: int, retry_queue_size: int):
        self.task_key = task_key
        self._scheduled_queue = asyncio.Queue(maxsize=scheduled_queue_size)
        self._retry_queue = asyncio.Queue(maxsize=retry_queue_size)

    async def get(self) -> schemas.core.TaskRun:
        # First, check if there's anything in the retry queue
        try:
            return self._retry_queue.get_nowait()
        except asyncio.QueueEmpty:
            return await self._scheduled_queue.get()

    async def put(self, task_run: schemas.core.TaskRun) -> None:
        await self._scheduled_queue.put(task_run)

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        await self._retry_queue.put(task_run)

    @classmethod
    @inject_db
    async def restore_scheduled_tasks_if_necessary(cls, db: PrefectDBInterface):
        """Restores scheduled task runs from the database, if necessary."""
        if cls._scheduled_tasks_already_restored:
            return

        cls._scheduled_tasks_already_restored = True

        if not PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING.value():
            return

        async with db.session_context() as session:
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

        if not task_runs:
            return

        for task_run_model in task_runs:
            task_run: schemas.core.TaskRun = schemas.core.TaskRun.from_orm(
                task_run_model
            )
            await cls.for_key(task_run.task_key).retry(task_run)

        logger.info("Restored %s scheduled task runs", len(task_runs))


class MultiQueue:
    """A queue that can pull tasks from from any of a number of task queues"""

    _queues: List[TaskQueue]

    def __init__(self, task_keys: List[str]):
        self._queues = [TaskQueue.for_key(task_key) for task_key in task_keys]

    async def get(self) -> schemas.core.TaskRun:
        """Gets the next task_run from any of the given queues"""
        await TaskQueue.restore_scheduled_tasks_if_necessary()

        # This implements a "race" among the queue.get() calls for each of the queues
        # by waiting for the first one to finish, reenqueing any ties, and then
        # cancelling any others

        loop = asyncio.get_event_loop()
        gets = [loop.create_task(queue.get()) for queue in self._queues]

        finishers, losers = await asyncio.wait(
            gets, return_when=asyncio.FIRST_COMPLETED
        )

        winner, *placers = finishers
        for future in placers:
            task_run = future.result()
            await TaskQueue.for_key(task_run.task_key).retry(task_run)

        for task in losers:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        return winner.result()


@router.websocket("/subscriptions/scheduled")
async def scheduled_task_subscription(websocket: WebSocket):
    websocket = await subscriptions.accept_prefect_socket(websocket)
    if not websocket:
        return

    subscription = await websocket.receive_json()
    task_keys = subscription.get("keys", [])
    if not task_keys:
        return

    subscribed_queue = MultiQueue(task_keys)

    while True:
        task_run = await subscribed_queue.get()

        try:
            await websocket.send_json(task_run.dict(json_compatible=True))

            await subscriptions.ping_pong(websocket)

        except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:
            # If sending fails or pong fails, put the task back into the retry queue
            await TaskQueue.for_key(task_run.task_key).retry(task_run)
            break
