from contextlib import asynccontextmanager
from typing import Any, Coroutine, Dict, Iterable, Optional, TypeVar
from uuid import UUID, uuid4

from typing_extensions import ParamSpec, Self

from prefect import Task, get_client
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import TaskRun
from prefect.futures import PrefectFuture
from prefect.states import StateType
from prefect.utilities.asyncutils import A, Async

P = ParamSpec("P")
R = TypeVar("R")


class TaskRunEngine:
    def __init__(
        self,
        task: Task,
        parameters: Optional[Dict[str, Any]] = None,
        task_run: Optional[TaskRun] = None,
        flow_run_id: Optional[UUID] = None,
    ):
        self.task = task
        self.parameters = parameters
        self.task_run = task_run
        self.flow_run_id = flow_run_id

    def is_running(self) -> bool:
        if self.task_run is None:
            return False
        return getattr(self.task_run, "state", None) == StateType.RUNNING

    async def handle_success(self, result):
        pass

    async def handle_exception(self, exc):
        pass

    async def create_task_run(self, client: PrefectClient) -> TaskRun:
        return await client.create_task_run(
            task=self.task,
            flow_run_id=self.flow_run_id,
            dynamic_key=uuid4().hex,
        )

    @asynccontextmanager
    async def start(self):
        """
        - check for a cached state
        - sets state to running
        - initialize task run logger
        - update task run name
        """
        async with get_client() as client:
            if self.task_run is None:
                self.task_run = await self.create_task_run(client)
            yield self

    async def __aenter__(self: "Self") -> "Self":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


async def run_task(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
) -> R | None:
    """
    Runs a task against the API.

    We will most likely want to use this logic as a wrapper and return a coroutine for type inference.
    """

    engine = TaskRunEngine(task, parameters, task_run)

    async with engine.start() as state:
        # This is a context manager that keeps track of the state of the task run.
        while state.is_running():
            try:
                # This is where the task is actually run.
                result = await task.fn(**parameters)  # type: ignore

                # If the task run is successful, finalize it.
                await state.handle_success(result)

                return result

            except Exception as exc:
                # If the task fails, and we have retries left, set the task to retrying.
                await state.handle_exception(exc)
