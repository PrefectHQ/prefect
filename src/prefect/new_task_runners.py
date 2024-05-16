import abc
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional

from typing_extensions import ParamSpec, Self, TypeVar

from prefect.logging.loggers import get_logger
from prefect.new_futures import PrefectConcurrentFuture, PrefectFuture

if TYPE_CHECKING:
    from prefect.tasks import Task

P = ParamSpec("P")
T = TypeVar("T")


class TaskRunner(abc.ABC):
    def __init__(self):
        self.logger = get_logger(f"task_runner.{self.name}")
        self._started = False

    @property
    def name(self):
        return type(self).__name__.lower().replace("taskrunner", "")

    @abc.abstractmethod
    def duplicate(self) -> Self:
        ...

    @abc.abstractmethod
    def submit(
        self,
        task: "Task",
        parameters: Dict[str, Any],
        wait_for: Iterable[PrefectFuture],
    ) -> PrefectFuture:
        ...

    def __enter__(self):
        if self._started:
            raise RuntimeError("This task runner is already started")

        self.logger.debug("Starting task runner")
        self._started = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.logger.debug("Stopping task runner")
        self._started = False


class ThreadPoolTaskRunner(TaskRunner):
    def __init__(self):
        super().__init__()
        self._executor: Optional[ThreadPoolExecutor] = None

    def duplicate(self) -> "ThreadPoolTaskRunner":
        return type(self)()

    def submit(
        self,
        task: "Task",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> PrefectConcurrentFuture:
        if not self._started or self._executor is None:
            raise RuntimeError("Task runner is not started")
        from prefect.new_task_engine import run_task_async, run_task_sync

        task_run_id = uuid.uuid4()
        context = copy_context()

        if task.isasync:
            future = self._executor.submit(
                context.run,
                asyncio.run,
                run_task_async(
                    task=task,
                    task_run_id=task_run_id,
                    parameters=parameters,
                    wait_for=wait_for,
                    return_type="state",
                ),
            )
        else:
            future = self._executor.submit(
                context.run,
                run_task_sync,
                task=task,
                task_run_id=task_run_id,
                parameters=parameters,
                wait_for=wait_for,
                return_type="state",
            )
        prefect_future = PrefectConcurrentFuture(
            task_run_id=task_run_id, wrapped_future=future
        )
        return prefect_future

    def __enter__(self):
        super().__enter__()
        self._executor = ThreadPoolExecutor()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._executor is not None:
            self._executor.shutdown()
            self._executor = None
        super().__exit__(exc_type, exc_value, traceback)
