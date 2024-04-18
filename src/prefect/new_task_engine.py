from contextlib import asynccontextmanager
from dataclasses import dataclass
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
from uuid import uuid4

from typing_extensions import ParamSpec

from prefect import Task, get_client
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import TaskRun
from prefect.context import FlowRunContext, TaskRunContext
from prefect.futures import PrefectFuture
from prefect.results import ResultFactory
from prefect.server.schemas.states import StateType
from prefect.states import Completed, Failed, Retrying, Running
from prefect.utilities.asyncutils import A, Async
from prefect.utilities.engine import _resolve_custom_task_run_name, propose_state

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class TaskRunEngine(Generic[P, R]):
    task: Task[P, Coroutine[Any, Any, R]]
    parameters: Optional[Dict[str, Any]] = None
    task_run: Optional[TaskRun] = None
    retries: int = 0
    _is_started: bool = False
    _client: Optional[PrefectClient] = None

    async def handle_success(self, result: R) -> R:
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        await propose_state(self._client, Completed(), task_run_id=self.task_run.id)
        return result

    async def handle_exception(self, exc: Exception):
        # If the task has retries left, and the retry condition is met, set the task to retrying.
        if not await self.handle_retry(exc):
            # If the task has no retries left, or the retry condition is not met, set the task to failed.
            await self.handle_failure(exc)

    async def handle_failure(self, exc: Exception) -> None:
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        state = await propose_state(
            self._client, Failed(), task_run_id=self.task_run.id
        )
        self.task_run.state = state
        self.task_run.state_name = state.name
        self.task_run.state_type = state.type
        self.retries = self.retries + 1
        raise exc

    async def handle_retry(self, exc: Exception) -> bool:
        """
        If the task has retries left, and the retry condition is met, set the task to retrying.
        - If the task has no retries left, or the retry condition is not met, return False.
        - If the task has retries left, and the retry condition is met, return True.
        """
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        if self.retries < self.task.retries:
            if not self.task.retry_condition_fn or self.task.retry_condition_fn(
                self.task, self.task_run, self.task_run.state
            ):
                state = await propose_state(
                    self._client, Retrying(), task_run_id=self.task_run.id
                )
                self.task_run.state = state
                self.task_run.state_name = state.name
                self.task_run.state_type = state.type
                self.retries = self.retries + 1
                return True
        return False

    async def create_task_run(self, client: PrefectClient) -> TaskRun:
        flow_run_ctx = FlowRunContext.get()
        try:
            task_run_name = _resolve_custom_task_run_name(
                self.task, self.parameters or {}
            )
        except TypeError:
            task_run_name = None
        task_run = await client.create_task_run(
            task=self.task,
            name=task_run_name,
            flow_run_id=getattr(flow_run_ctx.flow_run, "id", None)
            if flow_run_ctx and flow_run_ctx.flow_run
            else None,
            dynamic_key=uuid4().hex,
            state=Running(),
        )
        return task_run

    @asynccontextmanager
    async def start(self):
        """
        - check for a cached state
        - sets state to running
        - initialize task run logger
        - update task run name
        """
        async with get_client() as client:
            self._client = client
            self._is_started = True

            if not self.task_run:
                self.task_run = await self.create_task_run(client)

            with TaskRunContext(
                task=self.task,
                log_prints=self.task.log_prints or False,
                task_run=self.task_run,
                parameters=self.parameters or {},
                result_factory=await ResultFactory.from_autonomous_task(self.task),
                client=client,
            ):
                yield self

        self._is_started = False
        self._client = None

    async def get_client(self):
        if not self._is_started:
            raise RuntimeError("Engine has not started.")
        else:
            return self._client

    def is_running(self) -> bool:
        if self.task_run is None:
            return False
        return (
            getattr(getattr(self.task_run, "state", None), "type", None)
            == StateType.RUNNING
        )


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

    engine = TaskRunEngine[P, R](task, parameters, task_run)
    async with engine.start() as state:
        # This is a context manager that keeps track of the state of the task run.
        while state.is_running():
            try:
                # This is where the task is actually run.
                result = cast(R, await task.fn(**(parameters or {})))  # type: ignore
                # If the task run is successful, finalize it.
                await state.handle_success(result)
                return result

            except Exception as exc:
                # If the task fails, and we have retries left, set the task to retrying.
                await state.handle_exception(exc)
