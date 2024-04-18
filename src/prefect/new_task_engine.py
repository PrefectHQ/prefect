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
from uuid import UUID, uuid4

from typing_extensions import ParamSpec

from prefect import Task, get_client
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import TaskRun
from prefect.context import TaskRunContext
from prefect.futures import PrefectFuture
from prefect.results import ResultFactory
from prefect.server.schemas.states import StateType
from prefect.states import Running
from prefect.utilities.asyncutils import A, Async

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class TaskRunEngine(Generic[P, R]):
    task: Task[P, Coroutine[Any, Any, R]]
    parameters: Optional[Dict[str, Any]] = None
    task_run: Optional[TaskRun] = None
    flow_run_id: Optional[UUID] = None
    _is_started: bool = False
    _client: Optional[PrefectClient] = None

    async def handle_success(self, result: R):
        pass

    async def handle_exception(self, exc: Exception):
        pass

    async def create_task_run(self, client: PrefectClient) -> TaskRun:
        return await client.create_task_run(
            task=self.task,
            flow_run_id=self.flow_run_id,
            dynamic_key=uuid4().hex,
            state=Running(),
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
