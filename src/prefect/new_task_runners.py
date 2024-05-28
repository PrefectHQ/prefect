import abc
import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import TYPE_CHECKING, Any, Dict, Generic, Iterable, Optional, Set

from typing_extensions import ParamSpec, Self, TypeVar

from prefect.client.schemas.objects import TaskRunInput
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.new_futures import PrefectConcurrentFuture, PrefectFuture
from prefect.utilities.callables import (
    expand_mapping_parameters,
)

if TYPE_CHECKING:
    from prefect.tasks import Task

P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", bound=PrefectFuture)


class TaskRunner(abc.ABC, Generic[F]):
    """
    Abstract base class for task runners.

    A task runner is responsible for submitting tasks to the task run engine running
    in an execution environment. Submitted tasks are non-blocking and return a future
    object that can be used to wait for the task to complete and retrieve the result.

    Task runners are context managers and should be used in a `with` block to ensure
    proper cleanup of resources.
    """

    def __init__(self):
        self.logger = get_logger(f"task_runner.{self.name}")
        self._started = False

    @property
    def name(self):
        """The name of this task runner"""
        return type(self).__name__.lower().replace("taskrunner", "")

    @abc.abstractmethod
    def duplicate(self) -> Self:
        """Return a new instance of this task runner with the same configuration."""
        ...

    @abc.abstractmethod
    def submit(
        self,
        task: "Task",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> F:
        """
        Submit a task to the task run engine.

        Args:
            task: The task to submit.
            parameters: The parameters to use when running the task.
            wait_for: A list of futures that the task depends on.

        Returns:
            A future object that can be used to wait for the task to complete and
            retrieve the result.
        """
        ...

    def map(
        self,
        task: "Task",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> Iterable[F]:
        """
        Submit multiple tasks to the task run engine.

        Args:
            task: The task to submit.
            parameters: The parameters to use when running the task.
            wait_for: A list of futures that the task depends on.

        Returns:
            An iterable of future objects that can be used to wait for the tasks to
            complete and retrieve the results.
        """
        if not self._started:
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        from prefect.utilities.engine import (
            collect_task_run_inputs_sync,
            resolve_inputs_sync,
        )

        # We need to resolve some futures to map over their data, collect the upstream
        # links beforehand to retain relationship tracking.
        task_inputs = {
            k: collect_task_run_inputs_sync(v, max_depth=0)
            for k, v in parameters.items()
        }

        # Resolve the top-level parameters in order to get mappable data of a known length.
        # Nested parameters will be resolved in each mapped child where their relationships
        # will also be tracked.
        parameters = resolve_inputs_sync(parameters, max_depth=0)

        parameters_list = expand_mapping_parameters(task.fn, parameters)
        return [
            self.submit(
                task=task,
                parameters=parameters,
                wait_for=wait_for,
                dependencies=task_inputs,
            )
            for parameters in parameters_list
        ]

    def __enter__(self):
        if self._started:
            raise RuntimeError("This task runner is already started")

        self.logger.debug("Starting task runner")
        self._started = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.logger.debug("Stopping task runner")
        self._started = False


class ThreadPoolTaskRunner(TaskRunner[PrefectConcurrentFuture]):
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
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> PrefectConcurrentFuture:
        """
        Submit a task to the task run engine running in a separate thread.

        Args:
            task: The task to submit.
            parameters: The parameters to use when running the task.
            wait_for: A list of futures that the task depends on.

        Returns:
            A future object that can be used to wait for the task to complete and
            retrieve the result.
        """
        if not self._started or self._executor is None:
            raise RuntimeError("Task runner is not started")

        from prefect.context import FlowRunContext
        from prefect.new_task_engine import run_task_async, run_task_sync

        task_run_id = uuid.uuid4()
        context = copy_context()

        flow_run_ctx = FlowRunContext.get()
        if flow_run_ctx:
            get_run_logger(flow_run_ctx).info(
                f"Submitting task {task.name} to thread pool executor..."
            )
        else:
            self.logger.info(f"Submitting task {task.name} to thread pool executor...")

        if task.isasync:
            # TODO: Explore possibly using a long-lived thread with an event loop
            # for better performance
            future = self._executor.submit(
                context.run,
                asyncio.run,
                run_task_async(
                    task=task,
                    task_run_id=task_run_id,
                    parameters=parameters,
                    wait_for=wait_for,
                    return_type="state",
                    dependencies=dependencies,
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
                dependencies=dependencies,
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
