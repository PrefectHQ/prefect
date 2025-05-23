from __future__ import annotations

import abc
import asyncio
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from typing import (
    TYPE_CHECKING,
    Any,
    Coroutine,
    Generic,
    Iterable,
    overload,
)

from typing_extensions import ParamSpec, Self, TypeVar

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.objects import TaskRunInput
from prefect.exceptions import MappingLengthMismatch, MappingMissingIterable
from prefect.futures import (
    PrefectConcurrentFuture,
    PrefectDistributedFuture,
    PrefectFuture,
    PrefectFutureList,
)
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.settings import PREFECT_TASK_RUNNER_THREAD_POOL_MAX_WORKERS
from prefect.utilities.annotations import allow_failure, quote, unmapped
from prefect.utilities.callables import (
    collapse_variadic_parameters,
    explode_variadic_parameter,
    get_parameter_defaults,
)
from prefect.utilities.collections import isiterable

if TYPE_CHECKING:
    import logging

    from prefect.tasks import Task

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")
F = TypeVar("F", bound=PrefectFuture[Any], default=PrefectConcurrentFuture[Any])


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
        self.logger: "logging.Logger" = get_logger(f"task_runner.{self.name}")
        self._started = False

    @property
    def name(self) -> str:
        """The name of this task runner"""
        return type(self).__name__.lower().replace("taskrunner", "")

    @abc.abstractmethod
    def duplicate(self) -> Self:
        """Return a new instance of this task runner with the same configuration."""
        ...

    @overload
    @abc.abstractmethod
    def submit(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> F: ...

    @overload
    @abc.abstractmethod
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> F: ...

    @abc.abstractmethod
    def submit(
        self,
        task: "Task[P, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> F: ...

    def map(
        self,
        task: "Task[P, R]",
        parameters: dict[str, Any | unmapped[Any] | allow_failure[Any]],
        wait_for: Iterable[PrefectFuture[R]] | None = None,
    ) -> PrefectFutureList[F]:
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

        # Ensure that any parameters in kwargs are expanded before this check
        parameters = explode_variadic_parameter(task.fn, parameters)

        iterable_parameters: dict[str, Any] = {}
        static_parameters: dict[str, Any] = {}
        annotated_parameters: dict[str, Any] = {}
        for key, val in parameters.items():
            if isinstance(val, (allow_failure, quote)):
                # Unwrap annotated parameters to determine if they are iterable
                annotated_parameters[key] = val
                val = val.unwrap()

            if isinstance(val, unmapped):
                static_parameters[key] = val.value
            elif isiterable(val):
                iterable_parameters[key] = list(val)
            else:
                static_parameters[key] = val

        if not len(iterable_parameters):
            raise MappingMissingIterable(
                "No iterable parameters were received. Parameters for map must "
                f"include at least one iterable. Parameters: {parameters}"
            )

        iterable_parameter_lengths = {
            key: len(val) for key, val in iterable_parameters.items()
        }
        lengths = set(iterable_parameter_lengths.values())
        if len(lengths) > 1:
            raise MappingLengthMismatch(
                "Received iterable parameters with different lengths. Parameters for map"
                f" must all be the same length. Got lengths: {iterable_parameter_lengths}"
            )

        map_length = list(lengths)[0]

        futures: list[PrefectFuture[Any]] = []
        for i in range(map_length):
            call_parameters: dict[str, Any] = {
                key: value[i] for key, value in iterable_parameters.items()
            }
            call_parameters.update(
                {key: value for key, value in static_parameters.items()}
            )

            # Add default values for parameters; these are skipped earlier since they should
            # not be mapped over
            for key, value in get_parameter_defaults(task.fn).items():
                call_parameters.setdefault(key, value)

            # Re-apply annotations to each key again
            for key, annotation in annotated_parameters.items():
                call_parameters[key] = annotation.rewrap(call_parameters[key])

            # Collapse any previously exploded kwargs
            call_parameters = collapse_variadic_parameters(task.fn, call_parameters)

            futures.append(
                self.submit(
                    task=task,
                    parameters=call_parameters,
                    wait_for=wait_for,
                    dependencies=task_inputs,
                )
            )

        return PrefectFutureList(futures)

    def __enter__(self) -> Self:
        if self._started:
            raise RuntimeError("This task runner is already started")

        self.logger.debug("Starting task runner")
        self._started = True
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.logger.debug("Stopping task runner")
        self._started = False


class ThreadPoolTaskRunner(TaskRunner[PrefectConcurrentFuture[R]]):
    """
    A task runner that executes tasks in a separate thread pool.

    Attributes:
        max_workers: The maximum number of threads to use for executing tasks.
            Defaults to `PREFECT_TASK_RUNNER_THREAD_POOL_MAX_WORKERS` or `sys.maxsize`.

    Note:
        This runner uses `contextvars.copy_context()` for thread-safe context propagation.
        However, because contextvars are thread-local, frequent task submissions
        that modify context (e.g., using `prefect.tags` in a loop) can lead to
        new thread creation per task. This may cause an increase in threads and
        file descriptors, potentially hitting OS limits (`OSError: Too many open files`).
        If this occurs, consider minimizing context changes within looped tasks or
        adjusting system limits for open file descriptors.
    """

    def __init__(self, max_workers: int | None = None):
        super().__init__()
        self._executor: ThreadPoolExecutor | None = None
        self._max_workers = (
            (PREFECT_TASK_RUNNER_THREAD_POOL_MAX_WORKERS.value() or sys.maxsize)
            if max_workers is None
            else max_workers
        )
        self._cancel_events: dict[uuid.UUID, threading.Event] = {}

    def duplicate(self) -> "ThreadPoolTaskRunner[R]":
        return type(self)(max_workers=self._max_workers)

    @overload
    def submit(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]: ...

    @overload
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]: ...

    def submit(
        self,
        task: "Task[P, R | Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]:
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

        if wait_for and task.tags and (self._max_workers <= len(task.tags)):
            self.logger.warning(
                f"Task {task.name} has {len(task.tags)} tags but only {self._max_workers} workers available"
                "This may lead to dead-locks. Consider increasing the value of `PREFECT_TASK_RUNNER_THREAD_POOL_MAX_WORKERS` or `max_workers`."
            )

        from prefect.context import FlowRunContext
        from prefect.task_engine import run_task_async, run_task_sync

        task_run_id = uuid7()
        cancel_event = threading.Event()
        self._cancel_events[task_run_id] = cancel_event
        context = copy_context()

        flow_run_ctx = FlowRunContext.get()
        if flow_run_ctx:
            get_run_logger(flow_run_ctx).debug(
                f"Submitting task {task.name} to thread pool executor..."
            )
        else:
            self.logger.debug(f"Submitting task {task.name} to thread pool executor...")

        submit_kwargs: dict[str, Any] = dict(
            task=task,
            task_run_id=task_run_id,
            parameters=parameters,
            wait_for=wait_for,
            return_type="state",
            dependencies=dependencies,
            context=dict(cancel_event=cancel_event),
        )

        if task.isasync:
            # TODO: Explore possibly using a long-lived thread with an event loop
            # for better performance
            future = self._executor.submit(
                context.run,
                asyncio.run,
                run_task_async(**submit_kwargs),
            )
        else:
            future = self._executor.submit(
                context.run,
                run_task_sync,
                **submit_kwargs,
            )
        prefect_future = PrefectConcurrentFuture(
            task_run_id=task_run_id, wrapped_future=future
        )
        return prefect_future

    @overload
    def map(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectConcurrentFuture[R]]: ...

    @overload
    def map(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectConcurrentFuture[R]]: ...

    def map(
        self,
        task: "Task[P, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectConcurrentFuture[R]]:
        return super().map(task, parameters, wait_for)

    def cancel_all(self) -> None:
        for event in self._cancel_events.values():
            event.set()
            self.logger.debug("Set cancel event")

        if self._executor is not None:
            self._executor.shutdown(cancel_futures=True)
            self._executor = None

    def __enter__(self) -> Self:
        super().__enter__()
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.cancel_all()
        if self._executor is not None:
            self._executor.shutdown(cancel_futures=True)
            self._executor = None
        super().__exit__(exc_type, exc_value, traceback)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, ThreadPoolTaskRunner):
            return False
        return self._max_workers == value._max_workers


# Here, we alias ConcurrentTaskRunner to ThreadPoolTaskRunner for backwards compatibility
ConcurrentTaskRunner = ThreadPoolTaskRunner


class PrefectTaskRunner(TaskRunner[PrefectDistributedFuture[R]]):
    def __init__(self):
        super().__init__()

    def duplicate(self) -> "PrefectTaskRunner[R]":
        return type(self)()

    @overload
    def submit(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> PrefectDistributedFuture[R]: ...

    @overload
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> PrefectDistributedFuture[R]: ...

    def submit(
        self,
        task: "Task[P, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[TaskRunInput]] | None = None,
    ) -> PrefectDistributedFuture[R]:
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
        if not self._started:
            raise RuntimeError("Task runner is not started")
        from prefect.context import FlowRunContext

        flow_run_ctx = FlowRunContext.get()
        if flow_run_ctx:
            get_run_logger(flow_run_ctx).info(
                f"Submitting task {task.name} to for execution by a Prefect task worker..."
            )
        else:
            self.logger.info(
                f"Submitting task {task.name} to for execution by a Prefect task worker..."
            )

        return task.apply_async(
            kwargs=parameters, wait_for=wait_for, dependencies=dependencies
        )

    @overload
    def map(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectDistributedFuture[R]]: ...

    @overload
    def map(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectDistributedFuture[R]]: ...

    def map(
        self,
        task: "Task[P, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectDistributedFuture[R]]:
        return super().map(task, parameters, wait_for)
