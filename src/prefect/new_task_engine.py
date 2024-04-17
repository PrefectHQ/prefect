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


class TaskRunContext(BaseModel):
    value: str = "Running"
    history: List[str] = Field(
        default_factory=list, description="Convenience store for history of states"
    )
    retries: int = 0

    @property
    def is_running(self) -> bool:
        # This doesn't need to be a property, obviously.
        return self.value not in ["Completed", "Failed"]

    @property
    def is_retrying(self) -> bool:
        # This doesn't need to be a property, obviously.
        return self.value in ["Retrying"]

    async def __aenter__(self: "Self") -> "Self":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    def update(self, response: TaskRun) -> Self:
        self.value: str = cast(str, response.state_name)
        self.history = self.history + [self.value]
        return self


class Client:
    """
    This is a fake client that simulates the behavior of the Prefect API.
    """

    async def create_task_run(self, task: Task[P, Coroutine[Any, Any, R]]) -> TaskRun:
        return TaskRun(
            task_key=str(uuid4()), dynamic_key=str(uuid4()), state_name="Running"
        )

    async def set_failed(self, task_run: TaskRun, exc: Exception) -> TaskRun:
        return TaskRun(
            task_key=task_run.task_key,
            dynamic_key=task_run.dynamic_key,
            state_name="Failed",
            state_info=str(exc),
        )

    async def set_retrying(self, task_run: TaskRun) -> TaskRun:
        return TaskRun(
            task_key=task_run.task_key,
            dynamic_key=task_run.dynamic_key,
            state_name="Retrying",
        )

    async def finalize_run(self, task_run: TaskRun, result: Any) -> TaskRun:
        return TaskRun(
            task_key=task_run.task_key,
            dynamic_key=task_run.dynamic_key,
            state_name="Completed",
            result=result,
        )


client = Client()


async def run_task(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
) -> R:
    """
    Runs a task against the API.
    """

    if not task_run:
        # If no task run is provided, create a new one.
        task_run = await client.create_task_run(task)

    result = cast(R, None)  # Ask me about this sync.

    async with TaskRunContext() as state:
        # This is a context manager that keeps track of the state of the task run.
        while state.is_running:
            try:
                # This is where the task is actually run.
                result = await task.fn(**parameters)  # type: ignore

                # This is a random error that occurs 30% of the time.
                if random.random() < 0.7:
                    raise ValueError("This is a random error")

                # If the task run is successful, finalize it.
                state = state.update(await client.finalize_run(task_run, result))

            except Exception as exc:
                # If the task fails, and we have retries left, set the task to retrying.
                if task.retries > state.retries:
                    state = state.update(await client.set_retrying(task_run))
                    state.retries += 1
                    await asyncio.sleep(0)

                # If the task fails, and we have no retries left, set the task to failed.
                else:
                    state = state.update(await client.set_failed(task_run, exc))

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
#     Runs a task against the API.
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
