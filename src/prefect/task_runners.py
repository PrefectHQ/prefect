from __future__ import annotations

import abc
import asyncio
import concurrent.futures
import multiprocessing
import os
import sys
import threading
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextvars import copy_context
from types import CoroutineType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Iterable,
    overload,
)

from typing_extensions import ParamSpec, Self, TypeVar

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.objects import RunInput
from prefect.exceptions import MappingLengthMismatch, MappingMissingIterable
from prefect.futures import (
    PrefectConcurrentFuture,
    PrefectDistributedFuture,
    PrefectFuture,
    PrefectFutureList,
)
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.settings.context import get_current_settings
from prefect.utilities.annotations import allow_failure, quote, unmapped
from prefect.utilities.callables import (
    cloudpickle_wrapped_call,
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
        task: "Task[P, CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> F: ...

    @overload
    @abc.abstractmethod
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> F: ...

    @abc.abstractmethod
    def submit(
        self,
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> F: ...

    def map(
        self,
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
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

    Examples:
        Use a thread pool task runner with a flow:

        ```python
        from prefect import flow, task
        from prefect.task_runners import ThreadPoolTaskRunner

        @task
        def some_io_bound_task(x: int) -> int:
            # making a query to a database, reading a file, etc.
            return x * 2

        @flow(task_runner=ThreadPoolTaskRunner(max_workers=3)) # use at most 3 threads at a time
        def my_io_bound_flow():
            futures = []
            for i in range(10):
                future = some_io_bound_task.submit(i * 100)
                futures.append(future)

            return [future.result() for future in futures]
        ```

        Use a thread pool task runner as a context manager:

        ```python
        from prefect.task_runners import ThreadPoolTaskRunner

        @task
        def some_io_bound_task(x: int) -> int:
            # making a query to a database, reading a file, etc.
            return x * 2

        # Use the runner directly
        with ThreadPoolTaskRunner(max_workers=2) as runner:
            future1 = runner.submit(some_io_bound_task, {"x": 1})
            future2 = runner.submit(some_io_bound_task, {"x": 2})

            result1 = future1.result()  # 2
            result2 = future2.result()  # 4
        ```

        Configure max workers via settings:

        ```python
        # Set via environment variable
        # export PREFECT_TASK_RUNNER_THREAD_POOL_MAX_WORKERS=8

        from prefect import flow
        from prefect.task_runners import ThreadPoolTaskRunner

        @flow(task_runner=ThreadPoolTaskRunner())  # Uses 8 workers from setting
        def my_flow():
            ...
        ```

    """

    def __init__(self, max_workers: int | None = None):
        super().__init__()
        current_settings = get_current_settings()
        self._executor: ThreadPoolExecutor | None = None
        self._max_workers = (
            (current_settings.tasks.runner.thread_pool_max_workers or sys.maxsize)
            if max_workers is None
            else max_workers
        )
        self._cancel_events: dict[uuid.UUID, threading.Event] = {}

    def duplicate(self) -> "ThreadPoolTaskRunner[R]":
        return type(self)(max_workers=self._max_workers)

    @overload
    def submit(
        self,
        task: "Task[P, CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]: ...

    @overload
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]: ...

    def submit(
        self,
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
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
        task: "Task[P, CoroutineType[Any, Any, R]]",
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
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
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


def _run_task_in_subprocess(
    *args: Any,
    env: dict[str, str] | None = None,
    **kwargs: Any,
) -> Any:
    """
    Wrapper function to update environment variables and settings before running a task in a subprocess.
    """
    from prefect.context import hydrated_context
    from prefect.engine import handle_engine_signals
    from prefect.task_engine import run_task_async, run_task_sync

    # Update environment variables
    os.environ.update(env or {})

    # Extract context from kwargs
    context = kwargs.pop("context", None)

    with hydrated_context(context):
        with handle_engine_signals(kwargs.get("task_run_id")):
            # Determine if this is an async task
            task = kwargs.get("task")
            if task and task.isasync:
                # For async tasks, we need to create a new event loop
                import asyncio

                maybe_coro = run_task_async(*args, **kwargs)
                return asyncio.run(maybe_coro)
            else:
                return run_task_sync(*args, **kwargs)


class _UnpicklingFuture(concurrent.futures.Future[R]):
    """Wrapper for a Future that unpickles the result returned by cloudpickle_wrapped_call."""

    def __init__(self, wrapped_future: concurrent.futures.Future[bytes]):
        self.wrapped_future = wrapped_future

    def result(self, timeout: float | None = None) -> R:
        pickled_result = self.wrapped_future.result(timeout)
        import cloudpickle

        return cloudpickle.loads(pickled_result)

    def exception(self, timeout: float | None = None) -> BaseException | None:
        return self.wrapped_future.exception(timeout)

    def done(self) -> bool:
        return self.wrapped_future.done()

    def cancelled(self) -> bool:
        return self.wrapped_future.cancelled()

    def cancel(self) -> bool:
        return self.wrapped_future.cancel()

    def add_done_callback(
        self, fn: Callable[[concurrent.futures.Future[R]], object]
    ) -> None:
        def _fn(wrapped_future: concurrent.futures.Future[bytes]) -> None:
            import cloudpickle

            result = cloudpickle.loads(wrapped_future.result())
            fn(result)

        return self.wrapped_future.add_done_callback(_fn)


class ProcessPoolTaskRunner(TaskRunner[PrefectConcurrentFuture[Any]]):
    """
    A task runner that executes tasks in a separate process pool.

    This task runner uses `ProcessPoolExecutor` to run tasks in separate processes,
    providing true parallelism for CPU-bound tasks and process isolation. Tasks
    are executed with proper context propagation and error handling.

    Attributes:
        max_workers: The maximum number of processes to use for executing tasks.
            Defaults to `multiprocessing.cpu_count()` if `PREFECT_TASKS_RUNNER_PROCESS_POOL_MAX_WORKERS` is not set.

    Examples:
        Use a process pool task runner with a flow:

        ```python
        from prefect import flow, task
        from prefect.task_runners import ProcessPoolTaskRunner

        @task
        def compute_heavy_task(n: int) -> int:
            # CPU-intensive computation that benefits from process isolation
            return sum(i ** 2 for i in range(n))

        @flow(task_runner=ProcessPoolTaskRunner(max_workers=4))
        def my_flow():
            futures = []
            for i in range(10):
                future = compute_heavy_task.submit(i * 1000)
                futures.append(future)

            return [future.result() for future in futures]
        ```

        Use a process pool task runner as a context manager:

        ```python
        from prefect.task_runners import ProcessPoolTaskRunner

        @task
        def my_task(x: int) -> int:
            return x * 2

        # Use the runner directly
        with ProcessPoolTaskRunner(max_workers=2) as runner:
            future1 = runner.submit(my_task, {"x": 1})
            future2 = runner.submit(my_task, {"x": 2})

            result1 = future1.result()  # 2
            result2 = future2.result()  # 4
        ```

        Configure max workers via settings:

        ```python
        # Set via environment variable
        # export PREFECT_TASKS_RUNNER_PROCESS_POOL_MAX_WORKERS=8

        from prefect import flow
        from prefect.task_runners import ProcessPoolTaskRunner

        @flow(task_runner=ProcessPoolTaskRunner())  # Uses 8 workers from setting
        def my_flow():
            ...
        ```

    Note:
        Process pool task runners provide process isolation but have overhead for
        inter-process communication. They are most beneficial for CPU-bound tasks
        that can take advantage of multiple CPU cores. For I/O-bound tasks,
        consider using `ThreadPoolTaskRunner` instead.

        This runner uses the 'spawn' multiprocessing start method for cross-platform
        consistency and to avoid issues with shared state between processes.

        All task parameters and return values must be serializable with cloudpickle.
        The runner automatically handles context propagation and environment
        variable passing to subprocess workers.
    """

    def __init__(self, max_workers: int | None = None):
        super().__init__()
        current_settings = get_current_settings()
        self._executor: ProcessPoolExecutor | None = None
        self._max_workers = (
            max_workers
            or current_settings.tasks.runner.process_pool_max_workers
            or multiprocessing.cpu_count()
        )
        self._cancel_events: dict[uuid.UUID, multiprocessing.Event] = {}

    def duplicate(self) -> Self:
        return type(self)(max_workers=self._max_workers)

    @overload
    def submit(
        self,
        task: "Task[P, CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]: ...

    @overload
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]: ...

    def submit(
        self,
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> PrefectConcurrentFuture[R]:
        """
        Submit a task to the task run engine running in a separate process.

        Args:
            task: The task to submit.
            parameters: The parameters to use when running the task.
            wait_for: A list of futures that the task depends on.
            dependencies: A dictionary of dependencies for the task.

        Returns:
            A future object that can be used to wait for the task to complete and
            retrieve the result.
        """
        if not self._started or self._executor is None:
            raise RuntimeError("Task runner is not started")

        if wait_for and task.tags and (self._max_workers <= len(task.tags)):
            self.logger.warning(
                f"Task {task.name} has {len(task.tags)} tags but only {self._max_workers} workers available"
                "This may lead to dead-locks. Consider increasing the value of `PREFECT_TASKS_RUNNER_PROCESS_POOL_MAX_WORKERS` or `max_workers`."
            )

        from prefect.context import FlowRunContext

        task_run_id = uuid7()
        cancel_event = multiprocessing.Event()
        self._cancel_events[task_run_id] = cancel_event

        flow_run_ctx = FlowRunContext.get()
        if flow_run_ctx:
            get_run_logger(flow_run_ctx).debug(
                f"Submitting task {task.name} to process pool executor..."
            )
        else:
            self.logger.debug(
                f"Submitting task {task.name} to process pool executor..."
            )

        # Serialize the current context for the subprocess
        from prefect.context import serialize_context

        context = serialize_context()

        submit_kwargs: dict[str, Any] = dict(
            task=task,
            task_run_id=task_run_id,
            parameters=parameters,
            wait_for=wait_for,
            return_type="state",
            dependencies=dependencies,
            context=context,
        )

        # Prepare the cloudpickle wrapped call for subprocess execution
        wrapped_call = cloudpickle_wrapped_call(
            _run_task_in_subprocess,
            env=get_current_settings().to_environment_variables(exclude_unset=True)
            | os.environ,
            **submit_kwargs,
        )

        # Submit to executor and create a wrapper that unpickles the result
        raw_future = self._executor.submit(wrapped_call)

        # Create a PrefectConcurrentFuture that handles unpickling
        prefect_future: PrefectConcurrentFuture[R] = PrefectConcurrentFuture(
            task_run_id=task_run_id, wrapped_future=_UnpicklingFuture(raw_future)
        )
        return prefect_future

    @overload
    def map(
        self,
        task: "Task[P, CoroutineType[Any, Any, R]]",
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
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectConcurrentFuture[R]]:
        return super().map(task, parameters, wait_for)

    def cancel_all(self) -> None:
        # Clear cancel events first to avoid resource tracking issues
        events_to_set = list(self._cancel_events.values())
        self._cancel_events.clear()

        for event in events_to_set:
            try:
                event.set()
                self.logger.debug("Set cancel event")
            except (OSError, ValueError):
                # Ignore errors if event is already closed/invalid
                pass

        if self._executor is not None:
            self._executor.shutdown(cancel_futures=True, wait=True)
            self._executor = None

    def __enter__(self) -> Self:
        super().__enter__()
        # Use spawn method for cross-platform consistency and avoiding shared state issues
        mp_context = multiprocessing.get_context("spawn")
        self._executor = ProcessPoolExecutor(
            max_workers=self._max_workers, mp_context=mp_context
        )
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.cancel_all()
        # cancel_all() already shuts down the executor, but double-check
        if self._executor is not None:
            self._executor.shutdown(cancel_futures=True, wait=True)
            self._executor = None
        super().__exit__(exc_type, exc_value, traceback)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, ProcessPoolTaskRunner):
            return False
        return self._max_workers == value._max_workers


class PrefectTaskRunner(TaskRunner[PrefectDistributedFuture[R]]):
    def __init__(self):
        super().__init__()

    def duplicate(self) -> "PrefectTaskRunner[R]":
        return type(self)()

    @overload
    def submit(
        self,
        task: "Task[P, CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> PrefectDistributedFuture[R]: ...

    @overload
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
    ) -> PrefectDistributedFuture[R]: ...

    def submit(
        self,
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
        dependencies: dict[str, set[RunInput]] | None = None,
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
        task: "Task[P, CoroutineType[Any, Any, R]]",
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
        task: "Task[P, R | CoroutineType[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectDistributedFuture[R]]:
        return super().map(task, parameters, wait_for)
