import abc
import asyncio
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generic,
    Iterable,
    Optional,
    TypeVar,
)
from uuid import UUID

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import TaskRun
from prefect.client.utilities import get_or_create_client
from prefect.states import State
from prefect.utilities.asyncutils import A, run_sync

if TYPE_CHECKING:
    from prefect.tasks import Task


R = TypeVar("R")


class PrefectFuture(Generic[R, A]):
    """
    Represents the result of a computation happening in a task runner.

    When tasks are called, they are submitted to a task runner which creates a future
    for access to the state and result of the task.
    """

    def __init__(
        self,
        key: UUID,
        task_runner: "ConcurrentTaskRunner",
        _final_state: Optional[State[R]] = None,  # Exposed for testing
    ) -> None:
        self.key = key
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

    async def _wait(self, timeout=None):
        """
        Async implementation for `wait`
        """
        if self._final_state:
            return self._final_state

        future = asyncio.wrap_future(self._task_runner._futures[self.key])
        self._final_state = await future

        return self._final_state

    def result(self, timeout: Optional[float] = None, raise_on_failure: bool = True):
        """
        Wait for the run to finish and return the final state.

        If the timeout is reached before the run reaches a final state, a `TimeoutError`
        will be raised.

        If `raise_on_failure` is `True` and the task run failed, the task run's
        exception will be raised.
        """
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

    def get_state(self, client: PrefectClient = None):
        """
        Get the current state of the task run.
        """
        return run_sync(self._get_state(client))

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

    # primarily for backwards compatibility
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


class BaseTaskRunner(abc.ABC):
    @abc.abstractmethod
    def submit(
        self,
        task: "Task",
        parameters: Optional[Dict[str, Any]] = None,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> PrefectFuture:
        pass

    @abc.abstractmethod
    def wait(self, key: uuid.UUID, timeout: Optional[float] = None) -> Optional[State]:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class ConcurrentTaskRunner(BaseTaskRunner):
    def __init__(self):
        self._executor: Optional[ThreadPoolExecutor] = None
        self._futures = {}

    def submit(
        self,
        task: "Task",
        parameters: Optional[Dict[str, Any]] = None,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> PrefectFuture:
        from prefect.new_task_engine import run_task, run_task_sync

        if self._executor is None:
            raise ValueError("Task runner must be used as a context manager.")

        task_run_id = uuid.uuid4()

        future = PrefectFuture(key=task_run_id, task_runner=self)

        context = copy_context()

        if task.isasync:
            self._futures[task_run_id] = self._executor.submit(
                context.run,
                asyncio.run,
                run_task(task, task_run_id, parameters, wait_for, return_type="state"),
            )
        else:
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
        try:
            return future.result(timeout)
        except TimeoutError:
            return None

    def __enter__(self):
        self._executor = ThreadPoolExecutor().__enter__()
        return self

    def __exit__(self, *args):
        if self._executor is None:
            return
        self._executor.shutdown(*args)
        self._executor = None
