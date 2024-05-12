import inspect
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    Iterable,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
)

import pendulum
from typing_extensions import ParamSpec

from prefect import Task, get_client
from prefect.client.orchestration import SyncPrefectClient
from prefect.client.schemas import TaskRun
from prefect.context import FlowRunContext, TaskRunContext
from prefect.futures import PrefectFuture, resolve_futures_to_states
from prefect.logging.loggers import get_logger, task_run_logger
from prefect.results import ResultFactory
from prefect.server.schemas.states import State
from prefect.settings import PREFECT_TASKS_REFRESH_CACHE
from prefect.states import (
    Retrying,
    Running,
    StateDetails,
    exception_to_crashed_state,
    exception_to_failed_state,
    return_value_to_state,
)
from prefect.utilities.asyncutils import A, Async, run_sync
from prefect.utilities.callables import parameters_to_args_kwargs
from prefect.utilities.engine import (
    _get_hook_name,
    propose_state_sync,
)
from prefect.utilities.timeout import timeout, timeout_async

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class TaskRunEngine(Generic[P, R]):
    task: Union[Task[P, R], Task[P, Coroutine[Any, Any, R]]]
    logger: logging.Logger = field(default_factory=lambda: get_logger("engine"))
    parameters: Optional[Dict[str, Any]] = None
    task_run: Optional[TaskRun] = None
    retries: int = 0
    _is_started: bool = False
    _client: Optional[SyncPrefectClient] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}

    @property
    def client(self) -> SyncPrefectClient:
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        return self._client

    @property
    def state(self) -> State:
        if not self.task_run:
            raise ValueError("Task run is not set")
        return self.task_run.state

    @property
    def can_retry(self) -> bool:
        retry_condition: Optional[
            Callable[[Task[P, Coroutine[Any, Any, R]], TaskRun, State], bool]
        ] = self.task.retry_condition_fn
        if not self.task_run:
            raise ValueError("Task run is not set")
        return not retry_condition or retry_condition(
            self.task, self.task_run, self.state
        )

    def get_hooks(self, state: State, as_async: bool = False) -> Iterable[Callable]:
        task = self.task
        task_run = self.task_run

        if not task_run:
            raise ValueError("Task run is not set")

        hooks = None
        if state.is_failed() and task.on_failure:
            hooks = task.on_failure
        elif state.is_completed() and task.on_completion:
            hooks = task.on_completion

        for hook in hooks or []:
            hook_name = _get_hook_name(hook)

            @contextmanager
            def hook_context():
                try:
                    self.logger.info(
                        f"Running hook {hook_name!r} in response to entering state"
                        f" {state.name!r}"
                    )
                    yield
                except Exception:
                    self.logger.error(
                        f"An error was encountered while running hook {hook_name!r}",
                        exc_info=True,
                    )
                else:
                    self.logger.info(
                        f"Hook {hook_name!r} finished running successfully"
                    )

            if as_async:

                async def _hook_fn():
                    with hook_context():
                        result = hook(task, task_run, state)
                        if inspect.isawaitable(result):
                            await result
            else:

                def _hook_fn():
                    with hook_context():
                        hook(task, task_run, state)

            yield _hook_fn

    def _compute_state_details(
        self, include_cache_expiration: bool = False
    ) -> StateDetails:
        ## setup cache metadata
        task_run_context = TaskRunContext.get()
        cache_key = (
            self.task.cache_key_fn(
                task_run_context,
                self.parameters or {},
            )
            if self.task.cache_key_fn
            else None
        )
        # Ignore the cached results for a cache key, default = false
        # Setting on task level overrules the Prefect setting (env var)
        refresh_cache = (
            self.task.refresh_cache
            if self.task.refresh_cache is not None
            else PREFECT_TASKS_REFRESH_CACHE.value()
        )

        if include_cache_expiration:
            cache_expiration = (
                (pendulum.now("utc") + self.task.cache_expiration)
                if self.task.cache_expiration
                else None
            )
        else:
            cache_expiration = None
        return StateDetails(
            cache_key=cache_key,
            refresh_cache=refresh_cache,
            cache_expiration=cache_expiration,
        )

    def begin_run(self):
        state_details = self._compute_state_details()
        new_state = Running(state_details=state_details)
        state = self.set_state(new_state)
        while state.is_pending():
            time.sleep(0.2)
            state = self.set_state(new_state)

    def set_state(self, state: State, force: bool = False) -> State:
        if not self.task_run:
            raise ValueError("Task run is not set")
        new_state = propose_state_sync(
            self.client, state, task_run_id=self.task_run.id, force=force
        )
        # type: ignore

        # currently this is a hack to keep a reference to the state object
        # that has an in-memory result attached to it; using the API state
        # could result in losing that reference
        self.task_run.state = new_state
        return new_state

    def result(self, raise_on_failure: bool = True) -> "Union[R, State, None]":
        _result = self.state.result(raise_on_failure=raise_on_failure, fetch=True)
        # state.result is a `sync_compatible` function that may or may not return an awaitable
        # depending on whether the parent frame is sync or not
        if inspect.isawaitable(_result):
            _result = run_sync(_result)
        return _result

    def handle_success(self, result: R) -> R:
        result_factory = getattr(TaskRunContext.get(), "result_factory", None)
        if result_factory is None:
            raise ValueError("Result factory is not set")
        terminal_state = run_sync(
            return_value_to_state(
                run_sync(resolve_futures_to_states(result)),
                result_factory=result_factory,
            )
        )
        terminal_state.state_details = self._compute_state_details(
            include_cache_expiration=True
        )
        self.set_state(terminal_state)
        return result

    def handle_retry(self, exc: Exception) -> bool:
        """
        If the task has retries left, and the retry condition is met, set the task to retrying.
        - If the task has no retries left, or the retry condition is not met, return False.
        - If the task has retries left, and the retry condition is met, return True.
        """
        if self.retries < self.task.retries and self.can_retry:
            self.set_state(Retrying(), force=True)
            self.retries = self.retries + 1
            return True
        return False

    def handle_exception(self, exc: Exception) -> None:
        # If the task fails, and we have retries left, set the task to retrying.
        if not self.handle_retry(exc):
            # If the task has no retries left, or the retry condition is not met, set the task to failed.
            context = TaskRunContext.get()
            state = run_sync(
                exception_to_failed_state(
                    exc,
                    message="Task run encountered an exception",
                    result_factory=getattr(context, "result_factory", None),
                )
            )
            self.set_state(state)

    def handle_crash(self, exc: BaseException) -> None:
        state = run_sync(exception_to_crashed_state(exc))
        self.logger.error(f"Crash detected! {state.message}")
        self.logger.debug("Crash details:", exc_info=exc)
        self.set_state(state, force=True)

    @contextmanager
    def enter_run_context(self, client: Optional[SyncPrefectClient] = None):
        if client is None:
            client = self.client
        if not self.task_run:
            raise ValueError("Task run is not set")

        self.task_run = client.read_task_run(self.task_run.id)

        with TaskRunContext(
            task=self.task,
            log_prints=self.task.log_prints or False,
            task_run=self.task_run,
            parameters=self.parameters,
            result_factory=run_sync(ResultFactory.from_autonomous_task(self.task)),  # type: ignore
            client=client,
        ):
            # set the logger to the task run logger
            current_logger = self.logger
            try:
                self.logger = task_run_logger(task_run=self.task_run, task=self.task)  # type: ignore
                yield
            finally:
                self.logger = current_logger

    @contextmanager
    def start(self) -> Generator["TaskRunEngine", Any, Any]:
        """
        Enters a client context and creates a task run if needed.
        """
        with get_client(sync_client=True) as client:
            self._client = client
            self._is_started = True
            try:
                if not self.task_run:
                    self.task_run = run_sync(
                        self.task.create_run(
                            client=client,
                            parameters=self.parameters,
                            flow_run_context=FlowRunContext.get(),
                            parent_task_run_context=TaskRunContext.get(),
                        )
                    )

                yield self
            except Exception:
                # regular exceptions are caught and re-raised to the user
                raise
            except BaseException as exc:
                # BaseExceptions are caught and handled as crashes
                self.handle_crash(exc)
                raise
            finally:
                self._is_started = False
                self._client = None

    async def get_client(self):
        if not self._is_started:
            raise RuntimeError("Engine has not started.")
        else:
            return self._client

    def is_running(self) -> bool:
        if getattr(self, "task_run", None) is None:
            return False
        return getattr(self, "task_run").state.is_running()

    def is_pending(self) -> bool:
        if getattr(self, "task_run", None) is None:
            return False  # TODO: handle this differently?
        return getattr(self, "task_run").state.is_pending()


def run_task_sync(
    task: Task[P, R],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    engine = TaskRunEngine[P, R](task=task, parameters=parameters, task_run=task_run)

    # This is a context manager that keeps track of the run of the task run.
    with engine.start() as run:
        run.begin_run()

        while run.is_running():
            with run.enter_run_context():
                try:
                    # This is where the task is actually run.
                    with timeout(seconds=run.task.timeout_seconds):
                        call_args, call_kwargs = parameters_to_args_kwargs(
                            task.fn, run.parameters or {}
                        )
                        result = cast(R, task.fn(*call_args, **call_kwargs))  # type: ignore

                    # If the task run is successful, finalize it.
                    run.handle_success(result)

                except Exception as exc:
                    run.handle_exception(exc)

        if run.state.is_final():
            for hook in run.get_hooks(run.state):
                hook()

        if return_type == "state":
            return run.state
        return run.result()


async def run_task_async(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    """
    Runs a task against the API.

    We will most likely want to use this logic as a wrapper and return a coroutine for type inference.
    """
    engine = TaskRunEngine[P, R](task=task, parameters=parameters, task_run=task_run)

    # This is a context manager that keeps track of the run of the task run.
    with engine.start() as run:
        run.begin_run()

        while run.is_running():
            with run.enter_run_context():
                try:
                    # This is where the task is actually run.
                    with timeout_async(seconds=run.task.timeout_seconds):
                        call_args, call_kwargs = parameters_to_args_kwargs(
                            task.fn, run.parameters or {}
                        )
                        result = cast(R, await task.fn(*call_args, **call_kwargs))  # type: ignore

                    # If the task run is successful, finalize it.
                    run.handle_success(result)

                except Exception as exc:
                    run.handle_exception(exc)

        if run.state.is_final():
            for hook in run.get_hooks(run.state, as_async=True):
                await hook()

        if return_type == "state":
            return run.state
        return run.result()


def run_task(
    task: Task[P, R],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    kwargs = dict(
        task=task,
        task_run=task_run,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
    )
    if task.isasync:
        return run_task_async(**kwargs)
    else:
        return run_task_sync(**kwargs)
