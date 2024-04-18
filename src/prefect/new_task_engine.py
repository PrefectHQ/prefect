import asyncio
import random
from typing import Any, Coroutine, Dict, Iterable, List, Optional, TypeVar, cast
from uuid import uuid4

from pydantic import BaseModel, Field
from typing_extensions import ParamSpec, Self

from prefect import Task
from prefect.client.orchestration import get_client
from prefect.client.schemas import TaskRun
from prefect.context import EngineContext
from prefect.futures import PrefectFuture
from prefect.utilities.asyncutils import A, Async

P = ParamSpec("P")
R = TypeVar("R")


class TaskRunEngine:
    def __init__(self, task: Task, parameters: Dict[str, Any], task_run: TaskRun):
        self.task = task
        self.parameters = parameters
        self.task_run = task_run

        # bookkeeping fields
        self._is_started = False
        self._client = None

    async def start(self):
        """
        - check for a cached state
        - sets state to running
        - initialize task run logger
        - update task run name
        """
        with get_client() as client:
            self._client = client
            self._is_started = True
        self._client = None
        return self

    async def get_client(self):
        if not self._is_started:
            raise RuntimeError("Engine has not started.")
        else:
            return self._client

    async def is_running(self):
        pass

    async def handle_success(self, result):
        pass

    async def handle_exception(self, exc):
        pass

    async def __aenter__(self: "Self") -> "Self":
        return self

    async def __aexit__(self, *args: Any) -> None:
        self._is_started = False


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

    result = cast(R, None)  # Ask me about this sync.

    async with engine.start() as state:
        # This is a context manager that keeps track of the state of the task run.
        while state.is_running():
            try:
                # This is where the task is actually run.
                result = await task.fn(**parameters)  # type: ignore

                # If the task run is successful, finalize it.
                await state.handle_success(result)

            except Exception as exc:
                # If the task fails, and we have retries left, set the task to retrying.
                await state.handle_exception(exc)

    return result  # type: ignore
