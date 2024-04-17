import asyncio
import random
from typing import Any, Coroutine, Dict, Iterable, List, Optional, TypeVar, cast
from uuid import uuid4

from pydantic import BaseModel, Field
from typing_extensions import ParamSpec, Self

from prefect import Task
from prefect.client.schemas import TaskRun
from prefect.futures import PrefectFuture
from prefect.utilities.asyncutils import A, Async

P = ParamSpec("P")
R = TypeVar("R")


class TaskRun:
    def __init__(self, task, parameters, task_run_id, client):
        self.task = task
        self.parameters = parameters
        self.task_run_id = task_run_id
        self.client = client

    @classmethod
    async def create(self, task, parameters):
        """
        Constructs a class and registers with the API.
        """
        pass

    async def start(self):
        """
        - check for a cached state
        - sets state to running
        - initialize task run logger
        - update task run name
        """
        return self

    async def is_running(self):
        pass

    async def handle_success(self, result):
        pass

    async def handle_exception(self, exc):
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

    if not task_run:
        # If no task run is provided, create a new one.
        task_run = TaskRun.create(task, parameters)

    result = cast(R, None)  # Ask me about this sync.

    async with task_run.start() as state:
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


# This is a different swing at this that benefits from better typing, so we can create strongly typed params, etc.
# But I worry it's a little goofy.
#
# def create_something_something(
#     task: Task[P, Coroutine[Any, Any, R]],
#     task_run: Optional[TaskRun] = None,
#     wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
# ) -> Callable[P, Coroutine[Any, Any, R]]:
#     """
#     Turns a naked task into an `orchestrated task` whose execution is managed by the Prefect API.
#     """

#     async def orchestrated_task(*args: P.args, **kwargs: P.kwargs) -> R:
#         nonlocal task_run

#         if not task_run:
#             # If no task run is provided, create a new one.
#             task_run = await client.create_task_run(task)

#         result = cast(R, None)  # Ask me about this sync.

#         async with TaskRunContext() as state:
#             # This is a context manager that keeps track of the state of the task run.
#             while state.is_running:
#                 try:
#                     # This is where the task is actually run.
#                     result = await task.fn(*args, **kwargs)

#                     # This is a random error that occurs 30% of the time.
#                     if random.random() < 0.7:
#                         raise ValueError("This is a random error")

#                     # If the task run is successful, finalize it.
#                     state = state.update(await client.finalize_run(task_run, result))

#                 except Exception as exc:

#                     # If the task fails, and we have retries left, set the task to retrying.
#                     if task.retries > state.retries:
#                         state = state.update(await client.set_retrying(task_run))
#                         state.retries += 1
#                         await asyncio.sleep(0)

#                     # If the task fails, and we have no retries left, set the task to failed.
#                     else:
#                         state = state.update(await client.set_failed(task_run, exc))

#             return result

#     return orchestrated_task
