from typing import (
    Any,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    Optional,
    TypeVar,
    cast,
)

from typing_extensions import ParamSpec, Self

from prefect import Task
from prefect.client.schemas import TaskRun
from prefect.futures import PrefectFuture
from prefect.utilities.asyncutils import A, Async

P = ParamSpec("P")
R = TypeVar("R")


class TaskRunEngine(Generic[P, R]):
    def __init__(
        self,
        task: Task[P, Coroutine[Any, Any, R]],
        parameters: Optional[Dict[str, Any]],
        task_run: TaskRun,
    ):
        self.task = task
        self.parameters = parameters
        self.task_run = task_run

    async def start(self) -> "TaskRunEngine[P, R]":
        """
        - check for a cached state
        - sets state to running
        - initialize task run logger
        - update task run name
        """
        return self

    async def is_running(self) -> bool:
        return False

    async def handle_success(self, result: R):
        pass

    async def handle_exception(self, exc: Exception):
        pass

    async def __aenter__(self: "Self") -> "Self":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


async def run_task(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
) -> R:
    """
    Runs a task against the API.

    We will most likely want to use this logic as a wrapper and return a coroutine for type inference.
    """

    engine = TaskRunEngine(task, parameters, task_run)

    result = cast(R, None)

    async with await engine.start() as state:
        # This is a context manager that keeps track of the state of the task run.
        while await state.is_running():
            try:
                # This is where the task is actually run.
                result = cast(R, await task.fn(**parameters))

                # If the task run is successful, finalize it.
                await state.handle_success(result)

            except Exception as exc:
                # If the task fails, and we have retries left, set the task to retrying.
                await state.handle_exception(exc)

    return result
