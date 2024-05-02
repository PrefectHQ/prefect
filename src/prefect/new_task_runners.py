import asyncio
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Generic,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID

from prefect._internal.concurrency.api import create_call, from_async
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import TaskRun
from prefect.client.utilities import get_or_create_client
from prefect.states import State
from prefect.utilities.asyncutils import A, Async, Sync, run_sync, sync

if TYPE_CHECKING:
    from prefect.tasks import Task


R = TypeVar("R")


class PrefectFuture(Generic[R, A]):
    """
    Represents the result of a computation happening in a task runner.

    When tasks are called, they are submitted to a task runner which creates a future
    for access to the state and result of the task.

    Examples:
        Define a task that returns a string

        >>> from prefect import flow, task
        >>> @task
        >>> def my_task() -> str:
        >>>     return "hello"

        Calls of this task in a flow will return a future

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task.submit()  # PrefectFuture[str, Sync] includes result type
        >>>     future.task_run.id  # UUID for the task run

        Wait for the task to complete

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task.submit()
        >>>     final_state = future.wait()

        Wait N seconds for the task to complete

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task.submit()
        >>>     final_state = future.wait(0.1)
        >>>     if final_state:
        >>>         ... # Task done
        >>>     else:
        >>>         ... # Task not done yet

        Wait for a task to complete and retrieve its result

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task.submit()
        >>>     result = future.result()
        >>>     assert result == "hello"

        Wait N seconds for a task to complete and retrieve its result

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task.submit()
        >>>     result = future.result(timeout=5)
        >>>     assert result == "hello"

        Retrieve the state of a task without waiting for completion

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task.submit()
        >>>     state = future.get_state()
    """

    def __init__(
        self,
        key: UUID,
        task_runner: "ConcurrentTaskRunner",
        asynchronous: A = True,
        _final_state: Optional[State[R]] = None,  # Exposed for testing
    ) -> None:
        self.key = key
        self.asynchronous = asynchronous
        self._task_run = None
        self._final_state = _final_state
        self._exception: Optional[Exception] = None
        self._task_runner = task_runner

    @property
    def task_run(self) -> TaskRun:
        """
        The task run associated with this future
        """
        if self._task_run:
            return self._task_run

        client, _ = get_or_create_client()

        task_run = run_sync(client.read_task_run(self.key))
        self._task_run = task_run
        return task_run

    @overload
    def wait(
        self: "PrefectFuture[R, Async]", timeout: None = None
    ) -> Awaitable[State[R]]:
        ...

    @overload
    def wait(self: "PrefectFuture[R, Sync]", timeout: None = None) -> State[R]:
        ...

    @overload
    def wait(
        self: "PrefectFuture[R, Async]", timeout: float
    ) -> Awaitable[Optional[State[R]]]:
        ...

    @overload
    def wait(self: "PrefectFuture[R, Sync]", timeout: float) -> Optional[State[R]]:
        ...

    def wait(self, timeout=None):
        """
        Wait for the run to finish and return the final state

        If the timeout is reached before the run reaches a final state,
        `None` is returned.
        """
        if self._final_state:
            return self._final_state

        self._final_state = self._task_runner.wait(self.key, timeout)

        return self._final_state

    @overload
    async def _wait(self, timeout: None = None) -> State[R]:
        ...

    @overload
    async def _wait(self, timeout: float) -> Optional[State[R]]:
        ...

    async def _wait(self, timeout=None):
        """
        Async implementation for `wait`
        """
        if self._final_state:
            return self._final_state

        self._final_state = self._task_runner.wait(self.key, timeout)

        return self._final_state

    @overload
    def result(
        self: "PrefectFuture[R, Sync]",
        timeout: float = None,
        raise_on_failure: bool = True,
    ) -> R:
        ...

    @overload
    def result(
        self: "PrefectFuture[R, Sync]",
        timeout: float = None,
        raise_on_failure: bool = False,
    ) -> Union[R, Exception]:
        ...

    @overload
    def result(
        self: "PrefectFuture[R, Async]",
        timeout: float = None,
        raise_on_failure: bool = True,
    ) -> Awaitable[R]:
        ...

    @overload
    def result(
        self: "PrefectFuture[R, Async]",
        timeout: float = None,
        raise_on_failure: bool = False,
    ) -> Awaitable[Union[R, Exception]]:
        ...

    def result(self, timeout: float = None, raise_on_failure: bool = True):
        """
        Wait for the run to finish and return the final state.

        If the timeout is reached before the run reaches a final state, a `TimeoutError`
        will be raised.

        If `raise_on_failure` is `True` and the task run failed, the task run's
        exception will be raised.
        """
        result = create_call(
            self._result, timeout=timeout, raise_on_failure=raise_on_failure
        )
        if self.asynchronous:
            return from_async.call_soon_in_loop_thread(result).aresult()
        else:
            # we don't want to block the event loop on the loop thread with our sync execution
            return run_sync(
                self._result(timeout=timeout, raise_on_failure=raise_on_failure)
            )

    async def _result(self, timeout: float = None, raise_on_failure: bool = True):
        """
        Async implementation of `result`
        """
        final_state = await self._wait(timeout=timeout)
        if not final_state:
            raise TimeoutError("Call timed out before task finished.")
        return await final_state.result(raise_on_failure=raise_on_failure, fetch=True)

    @overload
    def get_state(
        self: "PrefectFuture[R, Async]", client: PrefectClient = None
    ) -> Awaitable[State[R]]:
        ...

    @overload
    def get_state(
        self: "PrefectFuture[R, Sync]", client: PrefectClient = None
    ) -> State[R]:
        ...

    def get_state(self, client: PrefectClient = None):
        """
        Get the current state of the task run.
        """
        if self.asynchronous:
            return cast(Awaitable[State[R]], self._get_state(client=client))
        else:
            return cast(State[R], sync(self._get_state, client=client))

    async def _get_state(self, client: Optional[PrefectClient] = None) -> State[R]:
        client, _ = get_or_create_client(client)
        # We must wait for the task run id to be populated
        await self._wait_for_submission()

        task_run = await client.read_task_run(self.task_run.id)

        if not task_run:
            raise RuntimeError("Future has no associated task run in the server.")

        # Update the task run reference
        self._task_run = task_run
        return task_run.state

    async def _wait_for_submission(self):
        pass

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"PrefectFuture({self.key!r})"

    def __bool__(self) -> bool:
        warnings.warn(
            (
                "A 'PrefectFuture' from a task call was cast to a boolean; "
                "did you mean to check the result of the task instead? "
                "e.g. `if my_task().result(): ...`"
            ),
            stacklevel=2,
        )
        return True


class ConcurrentTaskRunner:
    def __init__(self):
        self._executor: Optional[ThreadPoolExecutor] = None
        self._started = False
        self._futures = {}

    def submit(self, task: "Task", parameters: dict = None, wait_for: list = None):
        from prefect.new_task_engine import run_task, run_task_sync

        if self._executor is None or not self._started:
            raise ValueError("Task runner must be used as a context manager.")

        task_run_id = uuid.uuid4()

        future = PrefectFuture(key=task_run_id, task_runner=self)

        context = copy_context()

        if task.isasync:
            future.asynchronous = True
            self._futures[task_run_id] = self._executor.submit(
                context.run,
                asyncio.run,
                run_task(task, parameters, task_run_id, wait_for, return_type="state"),
            )
        else:
            future.asynchronous = False
            self._futures[task_run_id] = self._executor.submit(
                context.run,
                run_task_sync,
                task,
                task_run_id,
                parameters,
                wait_for,
                return_type="state",
            )

        return future

    def wait(self, key: uuid.UUID, timeout: Optional[float] = None):
        future = self._futures[key]
        return future.result(timeout)

    def __enter__(self):
        self._executor = ThreadPoolExecutor().__enter__()
        self._started = True
        return self

    def __exit__(self, *args):
        if not self._started or self._executor is None:
            return
        self._executor.__exit__(*args)
        self._executor = None
        self._started = False
