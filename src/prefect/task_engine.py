import inspect
import logging
import time
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from textwrap import dedent
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    Iterable,
    Literal,
    Optional,
    Sequence,
    Set,
    TypeVar,
    Union,
)
from uuid import UUID

import anyio
import pendulum
from typing_extensions import ParamSpec

from prefect import Task
from prefect.client.orchestration import SyncPrefectClient
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import State, TaskRunInput
from prefect.context import (
    ClientContext,
    FlowRunContext,
    TaskRunContext,
    hydrated_context,
)
from prefect.events.schemas.events import Event
from prefect.exceptions import (
    Abort,
    Pause,
    PrefectException,
    UpstreamTaskError,
)
from prefect.futures import PrefectFuture
from prefect.logging.loggers import get_logger, patch_print, task_run_logger
from prefect.records.result_store import ResultFactoryStore
from prefect.results import ResultFactory, _format_user_supplied_storage_key
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_TASKS_REFRESH_CACHE,
)
from prefect.states import (
    AwaitingRetry,
    Failed,
    Paused,
    Pending,
    Retrying,
    Running,
    exception_to_crashed_state,
    exception_to_failed_state,
    return_value_to_state,
)
from prefect.transactions import Transaction, transaction
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.callables import call_with_parameters, parameters_to_args_kwargs
from prefect.utilities.collections import visit_collection
from prefect.utilities.engine import (
    _get_hook_name,
    emit_task_run_state_change_event,
    link_state_to_result,
    propose_state_sync,
    resolve_to_final_result,
)
from prefect.utilities.math import clamped_poisson_interval
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
    wait_for: Optional[Iterable[PrefectFuture]] = None
    context: Optional[Dict[str, Any]] = None
    _initial_run_context: Optional[TaskRunContext] = None
    _is_started: bool = False
    _client: Optional[SyncPrefectClient] = None
    _task_name_set: bool = False
    _last_event: Optional[Event] = None

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
        try:
            self.logger.debug(
                f"Running `retry_condition_fn` check {retry_condition!r} for task"
                f" {self.task.name!r}"
            )
            return not retry_condition or retry_condition(
                self.task, self.task_run, self.state
            )
        except Exception:
            self.logger.error(
                (
                    "An error was encountered while running `retry_condition_fn` check"
                    f" '{retry_condition!r}' for task {self.task.name!r}"
                ),
                exc_info=True,
            )
            return False

    def call_hooks(self, state: State = None) -> Iterable[Callable]:
        if state is None:
            state = self.state
        task = self.task
        task_run = self.task_run

        if not task_run:
            raise ValueError("Task run is not set")

        if state.is_failed() and task.on_failure_hooks:
            hooks = task.on_failure_hooks
        elif state.is_completed() and task.on_completion_hooks:
            hooks = task.on_completion_hooks
        else:
            hooks = None

        for hook in hooks or []:
            hook_name = _get_hook_name(hook)

            try:
                self.logger.info(
                    f"Running hook {hook_name!r} in response to entering state"
                    f" {state.name!r}"
                )
                result = hook(task, task_run, state)
                if inspect.isawaitable(result):
                    run_coro_as_sync(result)
            except Exception:
                self.logger.error(
                    f"An error was encountered while running hook {hook_name!r}",
                    exc_info=True,
                )
            else:
                self.logger.info(f"Hook {hook_name!r} finished running successfully")

    def compute_transaction_key(self) -> str:
        key = None
        if self.task.cache_policy:
            flow_run_context = FlowRunContext.get()
            task_run_context = TaskRunContext.get()

            if flow_run_context:
                parameters = flow_run_context.parameters
            else:
                parameters = None

            key = self.task.cache_policy.compute_key(
                task_ctx=task_run_context,
                inputs=self.parameters,
                flow_parameters=parameters,
            )
        elif self.task.result_storage_key is not None:
            key = _format_user_supplied_storage_key(self.task.result_storage_key)
        return key

    def _resolve_parameters(self):
        if not self.parameters:
            return {}

        resolved_parameters = {}
        for parameter, value in self.parameters.items():
            try:
                resolved_parameters[parameter] = visit_collection(
                    value,
                    visit_fn=resolve_to_final_result,
                    return_data=True,
                    max_depth=-1,
                    remove_annotations=True,
                    context={},
                )
            except UpstreamTaskError:
                raise
            except Exception as exc:
                raise PrefectException(
                    f"Failed to resolve inputs in parameter {parameter!r}. If your"
                    " parameter type is not supported, consider using the `quote`"
                    " annotation to skip resolution of inputs."
                ) from exc

        self.parameters = resolved_parameters

    def _wait_for_dependencies(self):
        if not self.wait_for:
            return

        visit_collection(
            self.wait_for,
            visit_fn=resolve_to_final_result,
            return_data=False,
            max_depth=-1,
            remove_annotations=True,
            context={"current_task_run": self.task_run, "current_task": self.task},
        )

    def begin_run(self):
        try:
            self._resolve_parameters()
            self._wait_for_dependencies()
        except UpstreamTaskError as upstream_exc:
            state = self.set_state(
                Pending(
                    name="NotReady",
                    message=str(upstream_exc),
                ),
                # if orchestrating a run already in a pending state, force orchestration to
                # update the state name
                force=self.state.is_pending(),
            )
            return

        new_state = Running()
        state = self.set_state(new_state)

        BACKOFF_MAX = 10
        backoff_count = 0

        # TODO: Could this listen for state change events instead of polling?
        while state.is_pending() or state.is_paused():
            if backoff_count < BACKOFF_MAX:
                backoff_count += 1
            interval = clamped_poisson_interval(
                average_interval=backoff_count, clamping_factor=0.3
            )
            time.sleep(interval)
            state = self.set_state(new_state)

    def set_state(self, state: State, force: bool = False) -> State:
        last_state = self.state
        if not self.task_run:
            raise ValueError("Task run is not set")
        try:
            new_state = propose_state_sync(
                self.client, state, task_run_id=self.task_run.id, force=force
            )
        except Pause as exc:
            # We shouldn't get a pause signal without a state, but if this happens,
            # just use a Paused state to assume an in-process pause.
            new_state = exc.state if exc.state else Paused()
            if new_state.state_details.pause_reschedule:
                # If we're being asked to pause and reschedule, we should exit the
                # task and expect to be resumed later.
                raise

        # currently this is a hack to keep a reference to the state object
        # that has an in-memory result attached to it; using the API state

        # could result in losing that reference
        self.task_run.state = new_state
        # emit a state change event
        self._last_event = emit_task_run_state_change_event(
            task_run=self.task_run,
            initial_state=last_state,
            validated_state=self.task_run.state,
            follows=self._last_event,
        )
        return new_state

    def result(self, raise_on_failure: bool = True) -> "Union[R, State, None]":
        _result = self.state.result(raise_on_failure=raise_on_failure, fetch=True)
        # state.result is a `sync_compatible` function that may or may not return an awaitable
        # depending on whether the parent frame is sync or not
        if inspect.isawaitable(_result):
            _result = run_coro_as_sync(_result)
        return _result

    def handle_success(self, result: R, transaction: Transaction) -> R:
        result_factory = getattr(TaskRunContext.get(), "result_factory", None)
        if result_factory is None:
            raise ValueError("Result factory is not set")

        if self.task.cache_expiration is not None:
            expiration = pendulum.now("utc") + self.task.cache_expiration
        else:
            expiration = None

        terminal_state = run_coro_as_sync(
            return_value_to_state(
                result,
                result_factory=result_factory,
                key=transaction.key,
                expiration=expiration,
                # defer persistence to transaction commit
                defer_persistence=True,
            )
        )
        transaction.stage(
            terminal_state.data,
            on_rollback_hooks=self.task.on_rollback_hooks,
            on_commit_hooks=self.task.on_commit_hooks,
        )
        if transaction.is_committed():
            terminal_state.name = "Cached"
        self.set_state(terminal_state)
        return result

    def handle_retry(self, exc: Exception) -> bool:
        """Handle any task run retries.

        - If the task has retries left, and the retry condition is met, set the task to retrying and return True.
          - If the task has a retry delay, place in AwaitingRetry state with a delayed scheduled time.
        - If the task has no retries left, or the retry condition is not met, return False.
        """
        if self.retries < self.task.retries and self.can_retry:
            if self.task.retry_delay_seconds:
                delay = (
                    self.task.retry_delay_seconds[
                        min(self.retries, len(self.task.retry_delay_seconds) - 1)
                    ]  # repeat final delay value if attempts exceed specified delays
                    if isinstance(self.task.retry_delay_seconds, Sequence)
                    else self.task.retry_delay_seconds
                )
                new_state = AwaitingRetry(
                    scheduled_time=pendulum.now("utc").add(seconds=delay)
                )
            else:
                delay = None
                new_state = Retrying()

            self.logger.info(
                f"Task run failed with exception {exc!r} - "
                f"Retry {self.retries + 1}/{self.task.retries} will start "
                f"{str(delay) + ' second(s) from now' if delay else 'immediately'}"
            )

            self.set_state(new_state, force=True)
            self.retries = self.retries + 1
            return True
        elif self.retries >= self.task.retries:
            self.logger.error(
                f"Task run failed with exception {exc!r} - Retries are exhausted"
            )
            return False

        return False

    def handle_exception(self, exc: Exception) -> None:
        # If the task fails, and we have retries left, set the task to retrying.
        if not self.handle_retry(exc):
            # If the task has no retries left, or the retry condition is not met, set the task to failed.
            context = TaskRunContext.get()
            state = run_coro_as_sync(
                exception_to_failed_state(
                    exc,
                    message="Task run encountered an exception",
                    result_factory=getattr(context, "result_factory", None),
                )
            )
            self.set_state(state)

    def handle_timeout(self, exc: TimeoutError) -> None:
        if not self.handle_retry(exc):
            message = (
                f"Task run exceeded timeout of {self.task.timeout_seconds} seconds"
            )
            self.logger.error(message)
            state = Failed(
                data=exc,
                message=message,
                name="TimedOut",
            )
            self.set_state(state)

    def handle_crash(self, exc: BaseException) -> None:
        state = run_coro_as_sync(exception_to_crashed_state(exc))
        self.logger.error(f"Crash detected! {state.message}")
        self.logger.debug("Crash details:", exc_info=exc)
        self.set_state(state, force=True)

    @contextmanager
    def setup_run_context(self, client: Optional[SyncPrefectClient] = None):
        from prefect.utilities.engine import (
            _resolve_custom_task_run_name,
            should_log_prints,
        )

        if client is None:
            client = self.client
        if not self.task_run:
            raise ValueError("Task run is not set")

        self.task_run = client.read_task_run(self.task_run.id)
        with ExitStack() as stack:
            if log_prints := should_log_prints(self.task):
                stack.enter_context(patch_print())
            stack.enter_context(
                TaskRunContext(
                    task=self.task,
                    log_prints=log_prints,
                    task_run=self.task_run,
                    parameters=self.parameters,
                    result_factory=run_coro_as_sync(ResultFactory.from_task(self.task)),  # type: ignore
                    client=client,
                )
            )
            # set the logger to the task run logger
            self.logger = task_run_logger(task_run=self.task_run, task=self.task)  # type: ignore

            # update the task run name if necessary
            if not self._task_name_set and self.task.task_run_name:
                task_run_name = _resolve_custom_task_run_name(
                    task=self.task, parameters=self.parameters
                )
                self.client.set_task_run_name(
                    task_run_id=self.task_run.id, name=task_run_name
                )
                self.logger.extra["task_run_name"] = task_run_name
                self.logger.debug(
                    f"Renamed task run {self.task_run.name!r} to {task_run_name!r}"
                )
                self.task_run.name = task_run_name
                self._task_name_set = True
            yield

    @contextmanager
    def initialize_run(
        self,
        task_run_id: Optional[UUID] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> Generator["TaskRunEngine", Any, Any]:
        """
        Enters a client context and creates a task run if needed.
        """
        with hydrated_context(self.context):
            with ClientContext.get_or_create() as client_ctx:
                self._client = client_ctx.sync_client
                self._is_started = True
                try:
                    if not self.task_run:
                        self.task_run = run_coro_as_sync(
                            self.task.create_run(
                                id=task_run_id,
                                parameters=self.parameters,
                                flow_run_context=FlowRunContext.get(),
                                parent_task_run_context=TaskRunContext.get(),
                                wait_for=self.wait_for,
                                extra_task_inputs=dependencies,
                            )
                        )
                    # Emit an event to capture that the task run was in the `PENDING` state.
                    self._last_event = emit_task_run_state_change_event(
                        task_run=self.task_run,
                        initial_state=None,
                        validated_state=self.task_run.state,
                    )

                    with self.setup_run_context():
                        # setup_run_context might update the task run name, so log creation here
                        self.logger.info(
                            f"Created task run {self.task_run.name!r} for task {self.task.name!r}"
                        )
                        yield self

                except Exception:
                    # regular exceptions are caught and re-raised to the user
                    raise
                except (Pause, Abort) as exc:
                    # Do not capture internal signals as crashes
                    if isinstance(exc, Abort):
                        self.logger.error("Task run was aborted: %s", exc)
                    raise
                except GeneratorExit:
                    # Do not capture generator exits as crashes
                    raise
                except BaseException as exc:
                    # BaseExceptions are caught and handled as crashes
                    self.handle_crash(exc)
                    raise
                finally:
                    # If debugging, use the more complete `repr` than the usual `str` description
                    display_state = (
                        repr(self.state) if PREFECT_DEBUG_MODE else str(self.state)
                    )
                    level = logging.INFO if self.state.is_completed() else logging.ERROR
                    msg = f"Finished in state {display_state}"
                    if self.state.is_pending():
                        msg += (
                            "\nPlease wait for all submitted tasks to complete"
                            " before exiting your flow by calling `.wait()` on the "
                            "`PrefectFuture` returned from your `.submit()` calls."
                        )
                        msg += dedent(
                            """

                            Example:

                            from prefect import flow, task

                            @task
                            def say_hello(name):
                                print f"Hello, {name}!"

                            @flow
                            def example_flow():
                                say_hello.submit(name="Marvin)
                                say_hello.wait()

                            example_flow()
                                      """
                        )
                    self.logger.log(
                        level=level,
                        msg=msg,
                    )

                    self._is_started = False
                    self._client = None

    def is_running(self) -> bool:
        """Whether or not the engine is currently running a task."""
        if (task_run := getattr(self, "task_run", None)) is None:
            return False
        return task_run.state.is_running() or task_run.state.is_scheduled()

    async def wait_until_ready(self):
        """Waits until the scheduled time (if its the future), then enters Running."""
        if scheduled_time := self.state.state_details.scheduled_time:
            sleep_time = (scheduled_time - pendulum.now("utc")).total_seconds()
            await anyio.sleep(sleep_time if sleep_time > 0 else 0)
            self.set_state(
                Retrying() if self.state.name == "AwaitingRetry" else Running(),
                force=True,
            )

    # --------------------------
    #
    # The following methods compose the main task run loop
    #
    # --------------------------

    @contextmanager
    def start(
        self,
        task_run_id: Optional[UUID] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> Generator[None, None, None]:
        with self.initialize_run(task_run_id=task_run_id, dependencies=dependencies):
            self.begin_run()
            try:
                yield
            finally:
                self.call_hooks()

    @contextmanager
    def transaction_context(self) -> Generator[Transaction, None, None]:
        result_factory = getattr(TaskRunContext.get(), "result_factory", None)

        # refresh cache setting is now repurposes as overwrite transaction record
        overwrite = (
            self.task.refresh_cache
            if self.task.refresh_cache is not None
            else PREFECT_TASKS_REFRESH_CACHE.value()
        )
        with transaction(
            key=self.compute_transaction_key(),
            store=ResultFactoryStore(result_factory=result_factory),
            overwrite=overwrite,
        ) as txn:
            yield txn

    @contextmanager
    def run_context(self):
        timeout_context = timeout_async if self.task.isasync else timeout
        # reenter the run context to ensure it is up to date for every run
        with self.setup_run_context():
            try:
                with timeout_context(seconds=self.task.timeout_seconds):
                    self.logger.debug(
                        f"Executing task {self.task.name!r} for task run {self.task_run.name!r}..."
                    )
                    yield self
            except TimeoutError as exc:
                self.handle_timeout(exc)
            except Exception as exc:
                self.handle_exception(exc)

    def call_task_fn(
        self, transaction: Transaction
    ) -> Union[R, Coroutine[Any, Any, R]]:
        """
        Convenience method to call the task function. Returns a coroutine if the
        task is async.
        """
        parameters = self.parameters or {}
        if self.task.isasync:

            async def _call_task_fn():
                if transaction.is_committed():
                    result = transaction.read()
                else:
                    result = await call_with_parameters(self.task.fn, parameters)
                self.handle_success(result, transaction=transaction)

            return _call_task_fn()
        else:
            if transaction.is_committed():
                result = transaction.read()
            else:
                result = call_with_parameters(self.task.fn, parameters)
            self.handle_success(result, transaction=transaction)


def run_task_sync(
    task: Task[P, R],
    task_run_id: Optional[UUID] = None,
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
    dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Union[R, State, None]:
    engine = TaskRunEngine[P, R](
        task=task,
        parameters=parameters,
        task_run=task_run,
        wait_for=wait_for,
        context=context,
    )

    with engine.start(task_run_id=task_run_id, dependencies=dependencies):
        while engine.is_running():
            run_coro_as_sync(engine.wait_until_ready())
            with engine.run_context(), engine.transaction_context() as txn:
                engine.call_task_fn(txn)

    return engine.state if return_type == "state" else engine.result()


async def run_task_async(
    task: Task[P, R],
    task_run_id: Optional[UUID] = None,
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
    dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Union[R, State, None]:
    engine = TaskRunEngine[P, R](
        task=task,
        parameters=parameters,
        task_run=task_run,
        wait_for=wait_for,
        context=context,
    )

    with engine.start(task_run_id=task_run_id, dependencies=dependencies):
        while engine.is_running():
            await engine.wait_until_ready()
            with engine.run_context(), engine.transaction_context() as txn:
                await engine.call_task_fn(txn)

    return engine.state if return_type == "state" else engine.result()


def run_generator_task_sync(
    task: Task[P, R],
    task_run_id: Optional[UUID] = None,
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
    dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Generator[R, None, None]:
    if return_type != "result":
        raise ValueError("The return_type for a generator task must be 'result'")

    engine = TaskRunEngine[P, R](
        task=task,
        parameters=parameters,
        task_run=task_run,
        wait_for=wait_for,
        context=context,
    )

    with engine.start(task_run_id=task_run_id, dependencies=dependencies):
        while engine.is_running():
            run_coro_as_sync(engine.wait_until_ready())
            with engine.run_context(), engine.transaction_context() as txn:
                # TODO: generators should default to commit_mode=OFF
                # because they are dynamic by definition
                # for now we just prevent this branch explicitly
                if False and txn.is_committed():
                    txn.read()
                else:
                    call_args, call_kwargs = parameters_to_args_kwargs(
                        task.fn, engine.parameters or {}
                    )
                    gen = task.fn(*call_args, **call_kwargs)
                    try:
                        while True:
                            gen_result = next(gen)
                            # link the current state to the result for dependency tracking
                            #
                            # TODO: this could grow the task_run_result
                            # dictionary in an unbounded way, so finding a
                            # way to periodically clean it up (using
                            # weakrefs or similar) would be good
                            link_state_to_result(engine.state, gen_result)
                            yield gen_result
                    except StopIteration as exc:
                        engine.handle_success(exc.value, transaction=txn)
                    except GeneratorExit as exc:
                        engine.handle_success(None, transaction=txn)
                        gen.throw(exc)

    return engine.result()


async def run_generator_task_async(
    task: Task[P, R],
    task_run_id: Optional[UUID] = None,
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
    dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[R, None]:
    if return_type != "result":
        raise ValueError("The return_type for a generator task must be 'result'")
    engine = TaskRunEngine[P, R](
        task=task,
        parameters=parameters,
        task_run=task_run,
        wait_for=wait_for,
        context=context,
    )

    with engine.start(task_run_id=task_run_id, dependencies=dependencies):
        while engine.is_running():
            await engine.wait_until_ready()
            with engine.run_context(), engine.transaction_context() as txn:
                # TODO: generators should default to commit_mode=OFF
                # because they are dynamic by definition
                # for now we just prevent this branch explicitly
                if False and txn.is_committed():
                    txn.read()
                else:
                    call_args, call_kwargs = parameters_to_args_kwargs(
                        task.fn, engine.parameters or {}
                    )
                    gen = task.fn(*call_args, **call_kwargs)
                    try:
                        while True:
                            # can't use anext in Python < 3.10
                            gen_result = await gen.__anext__()
                            # link the current state to the result for dependency tracking
                            #
                            # TODO: this could grow the task_run_result
                            # dictionary in an unbounded way, so finding a
                            # way to periodically clean it up (using
                            # weakrefs or similar) would be good
                            link_state_to_result(engine.state, gen_result)
                            yield gen_result
                    except (StopAsyncIteration, GeneratorExit) as exc:
                        engine.handle_success(None, transaction=txn)
                        if isinstance(exc, GeneratorExit):
                            gen.throw(exc)

    # async generators can't return, but we can raise failures here
    if engine.state.is_failed():
        engine.result()


def run_task(
    task: Task[P, Union[R, Coroutine[Any, Any, R]]],
    task_run_id: Optional[UUID] = None,
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
    dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Union[R, State, None, Coroutine[Any, Any, Union[R, State, None]]]:
    """
    Runs the provided task.

    Args:
        task: The task to run
        task_run_id: The ID of the task run; if not provided, a new task run
            will be created
        task_run: The task run object; if not provided, a new task run
            will be created
        parameters: The parameters to pass to the task
        wait_for: A list of futures to wait for before running the task
        return_type: The return type to return; either "state" or "result"
        dependencies: A dictionary of task run inputs to use for dependency tracking
        context: A dictionary containing the context to use for the task run; only
            required if the task is running on in a remote environment

    Returns:
        The result of the task run
    """
    kwargs = dict(
        task=task,
        task_run_id=task_run_id,
        task_run=task_run,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
        dependencies=dependencies,
        context=context,
    )
    if task.isasync and task.isgenerator:
        return run_generator_task_async(**kwargs)
    elif task.isgenerator:
        return run_generator_task_sync(**kwargs)
    elif task.isasync:
        return run_task_async(**kwargs)
    else:
        return run_task_sync(**kwargs)
