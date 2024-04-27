import asyncio
import inspect
import logging
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    Iterable,
    List,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
)
from uuid import uuid4

import pendulum
from typing_extensions import ParamSpec

from prefect import Task, get_client
from prefect._internal.concurrency.cancellation import (
    AlarmCancelScope,
    AsyncCancelScope,
    CancelledError,
)
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import TaskRunResult
from prefect.context import FlowRunContext, TaskRunContext
from prefect.futures import PrefectFuture, resolve_futures_to_states
from prefect.logging.loggers import get_logger, task_run_logger
from prefect.results import ResultFactory
from prefect.server.schemas.states import State
from prefect.settings import PREFECT_TASKS_REFRESH_CACHE
from prefect.states import (
    Pending,
    Retrying,
    Running,
    StateDetails,
    exception_to_crashed_state,
    exception_to_failed_state,
    return_value_to_state,
)
from prefect.utilities.asyncutils import A, Async, is_async_fn, run_sync
from prefect.utilities.engine import (
    _dynamic_key_for_task_run,
    _get_hook_name,
    _resolve_custom_task_run_name,
    collect_task_run_inputs,
    link_state_to_result,
    propose_state,
)

P = ParamSpec("P")
R = TypeVar("R")


@asynccontextmanager
async def timeout(seconds: float):
    try:
        with AsyncCancelScope(timeout=seconds):
            yield
    except CancelledError:
        raise TimeoutError(f"Task timed out after {seconds} second(s).")


@contextmanager
def timeout_sync(seconds: float):
    try:
        with AlarmCancelScope(timeout=seconds):
            yield
    except CancelledError:
        raise TimeoutError(f"Task timed out after {seconds} second(s).")


@dataclass
class TaskRunEngine(Generic[P, R]):
    task: Task[P, Coroutine[Any, Any, R]]
    logger: logging.Logger = field(default_factory=lambda: get_logger("engine"))
    parameters: Optional[Dict[str, Any]] = None
    task_run: Optional[TaskRun] = None
    retries: int = 0
    _is_started: bool = False
    _client: Optional[PrefectClient] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}

    @property
    def client(self) -> PrefectClient:
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        return self._client

    @property
    def state(self) -> State:
        return self.task_run.state  # type: ignore

    @property
    def can_retry(self) -> bool:
        retry_condition: Optional[  # type: ignore
            Callable[[Task[P, Coroutine[Any, Any, R]], TaskRun, State], bool]
        ] = self.task.retry_condition_fn  # type: ignore
        return not retry_condition or retry_condition(
            self.task, self.task_run, self.state
        )  # type: ignore

    async def _run_hooks(self, state: State) -> None:
        """Run the on_failure and on_completion hooks for a task, making sure to
        catch and log any errors that occur.
        """
        task = self.task
        task_run = self.task_run

        hooks = None
        if state.is_failed() and task.on_failure:
            hooks = task.on_failure
        elif state.is_completed() and task.on_completion:
            hooks = task.on_completion

        if hooks:
            for hook in hooks:
                hook_name = _get_hook_name(hook)
                try:
                    self.logger.info(
                        f"Running hook {hook_name!r} in response to entering state"
                        f" {state.name!r}"
                    )
                    if is_async_fn(hook):
                        await hook(task=task, task_run=task_run, state=state)
                    else:
                        hook(task=task, task_run=task_run, state=state)
                except Exception:
                    self.logger.error(
                        f"An error was encountered while running hook {hook_name!r}",
                        exc_info=True,
                    )
                else:
                    self.logger.info(
                        f"Hook {hook_name!r} finished running successfully"
                    )

    def _compute_state_details(
        self, include_cache_expiration: bool = False
    ) -> StateDetails:
        ## setup cache metadata
        task_run_context = TaskRunContext.get()
        cache_key = (
            self.task.cache_key_fn(
                task_run_context,
                self.parameters,
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

    async def begin_run(self) -> State:
        state_details = self._compute_state_details()
        new_state = Running(state_details=state_details)
        state = await self.set_state(new_state)
        while state.is_pending():
            await asyncio.sleep(1)
            state = await self.set_state(new_state)

    async def set_state(self, state: State, force: bool = False) -> State:
        new_state = await propose_state(
            self.client, state, task_run_id=self.task_run.id, force=force
        )  # type: ignore

        # currently this is a hack to keep a reference to the state object
        # that has an in-memory result attached to it; using the API state
        # could result in losing that reference
        self.task_run.state = new_state
        if new_state.is_final():
            await self._run_hooks(new_state)
        return new_state

    async def result(self, raise_on_failure: bool = True) -> "Union[R, State, None]":
        _result = self.state.result(raise_on_failure=raise_on_failure, fetch=True)
        # state.result is a `sync_compatible` function that may or may not return an awaitable
        # depending on whether the parent frame is sync or not
        if inspect.isawaitable(_result):
            _result = await _result
        return _result

    async def handle_success(self, result: R) -> R:
        result_factory = getattr(TaskRunContext.get(), "result_factory", None)
        terminal_state = await return_value_to_state(
            await resolve_futures_to_states(result),
            result_factory=result_factory,
        )
        terminal_state.state_details = self._compute_state_details(
            include_cache_expiration=True
        )
        await self.set_state(terminal_state)
        return result

    async def handle_retry(self, exc: Exception) -> bool:
        """
        If the task has retries left, and the retry condition is met, set the task to retrying.
        - If the task has no retries left, or the retry condition is not met, return False.
        - If the task has retries left, and the retry condition is met, return True.
        """
        if self.retries < self.task.retries and self.can_retry:
            await self.set_state(Retrying(), force=True)
            self.retries = self.retries + 1
            return True
        return False

    async def handle_exception(self, exc: Exception) -> None:
        # If the task fails, and we have retries left, set the task to retrying.
        if not await self.handle_retry(exc):
            # If the task has no retries left, or the retry condition is not met, set the task to failed.
            context = TaskRunContext.get()
            state = await exception_to_failed_state(
                exc,
                message="Task run encountered an exception",
                result_factory=getattr(context, "result_factory", None),
            )
            await self.set_state(state)

    async def handle_crash(self, exc: BaseException) -> None:
        state = await exception_to_crashed_state(exc)
        self.logger.error(f"Crash detected! {state.message}")
        self.logger.debug("Crash details:", exc_info=exc)
        await self.set_state(state, force=True)

    def infer_parent_task_runs(
        self, flow_run_ctx: FlowRunContext
    ) -> List[TaskRunResult]:
        """
        Infer parent task runs.

        1. Check if this task is running inside an existing task run context in
           the same flow run. If so, this is a nested task and the existing task
           run is a parent.
        2. Check if any of the inputs to this task correspond to states that are
           still running. If so, consider those task runs as parents. Note this
           under normal circumstances this probably only applies to values that
           were yielded from generator tasks.
        """
        parents = []

        # check if this task has a parent task run based on running in another
        # task run's existing context. A task run is only considered a parent if
        # it is in the same flow run (because otherwise presumably the child is
        # in a subflow, so the subflow serves as the parent) or if there is no
        # flow run
        task_run_ctx = TaskRunContext.get()
        if task_run_ctx:
            # there is no flow run
            if not flow_run_ctx:
                parents.append(TaskRunResult(id=task_run_ctx.task_run.id))
            # there is a flow run and the task run is in the same flow run
            elif (
                flow_run_ctx
                and task_run_ctx.task_run.flow_run_id == flow_run_ctx.flow_run.id
            ):
                parents.append(TaskRunResult(id=task_run_ctx.task_run.id))

        # parent dependency tracking: for every provided parameter value, try to
        # load the corresponding task run state. If the task run state is still
        # running, we consider it a parent task run. Note this is only done if
        # there is an active flow run context because dependencies are only
        # tracked within the same flow run.
        if flow_run_ctx:
            for v in self.parameters.values():
                if isinstance(v, State):
                    upstream_state = v
                else:
                    upstream_state = flow_run_ctx.task_run_results.get(id(v))
                if upstream_state and upstream_state.is_running():
                    parents.append(
                        TaskRunResult(id=upstream_state.state_details.task_run_id)
                    )

        return parents

    async def create_task_run(self, client: PrefectClient) -> TaskRun:
        flow_run_ctx = FlowRunContext.get()
        try:
            task_run_name = _resolve_custom_task_run_name(self.task, self.parameters)
        except TypeError:
            task_run_name = None

        # upstream dependency tracking: for every provided parameter value, try
        # to load the corresponding task run state
        task_inputs = {
            k: await collect_task_run_inputs(v) for k, v in self.parameters.items()
        }

        if task_parents := self.infer_parent_task_runs(flow_run_ctx):
            task_inputs["__parents__"] = task_parents

        # TODO: implement wait_for
        #        if wait_for:
        #            task_inputs["wait_for"] = await collect_task_run_inputs(wait_for)

        if flow_run_ctx:
            dynamic_key = _dynamic_key_for_task_run(
                context=flow_run_ctx, task=self.task
            )
        else:
            dynamic_key = uuid4().hex
        task_run = await client.create_task_run(
            task=self.task,
            name=task_run_name,
            flow_run_id=(
                getattr(flow_run_ctx.flow_run, "id", None)
                if flow_run_ctx and flow_run_ctx.flow_run
                else None
            ),
            dynamic_key=dynamic_key,
            state=Pending(),
            task_inputs=task_inputs,
        )
        return task_run

    @asynccontextmanager
    async def enter_run_context(self, client: Optional[PrefectClient] = None):
        if client is None:
            client = self.client

        self.task_run = await client.read_task_run(self.task_run.id)

        with TaskRunContext(
            task=self.task,
            log_prints=self.task.log_prints or False,
            task_run=self.task_run,
            parameters=self.parameters,
            result_factory=await ResultFactory.from_autonomous_task(self.task),
            client=client,
        ):
            self.logger = task_run_logger(task_run=self.task_run, task=self.task)
            yield

    @contextmanager
    def enter_run_context_sync(self, client: PrefectClient = None):
        if client is None:
            client = self.client

        self.task_run = run_sync(client.read_task_run(self.task_run.id))

        with TaskRunContext(
            task=self.task,
            log_prints=self.task.log_prints or False,
            task_run=self.task_run,
            parameters=self.parameters,
            result_factory=run_sync(ResultFactory.from_autonomous_task(self.task)),
            client=client,
        ):
            self.logger = task_run_logger(task_run=self.task_run, task=self.task)
            yield

    @asynccontextmanager
    async def start(self):
        """
        Enters a client context and creates a task run if needed.
        """
        async with get_client() as client:
            self._client = client
            self._is_started = True
            try:
                if not self.task_run:
                    self.task_run = await self.create_task_run(client)
                yield self
            except Exception:
                # regular exceptions are caught and re-raised to the user
                raise
            except BaseException as exc:
                # BaseExceptions are caught and handled as crashes
                await self.handle_crash(exc)
                raise
            finally:
                self._is_started = False
                self._client = None

    @contextmanager
    def start_sync(self):
        """
        Enters a client context and creates a task run if needed.
        """
        client = get_client()
        run_sync(client.__aenter__())
        self._client = client
        self._is_started = True
        try:
            if not self.task_run:
                self.task_run = run_sync(self.create_task_run(client))
            yield self
        except Exception:
            # regular exceptions are caught and re-raised to the user
            raise
        except BaseException as exc:
            # BaseExceptions are caught and handled as crashes
            run_sync(self.handle_crash(exc))
            raise
        finally:
            # quickly close client
            run_sync(client.__aexit__(None, None, None))
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


async def run_async_task(
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
    async with engine.start() as run:
        # This is a context manager that keeps track of the run of the task run.
        await run.begin_run()

        while run.is_running():
            async with run.enter_run_context():
                try:
                    # This is where the task is actually run.
                    async with timeout(run.task.timeout_seconds):
                        result = cast(R, await task.fn(**(parameters or {})))  # type: ignore

                    # If the task run is successful, finalize it.
                    await run.handle_success(result)
                    if return_type == "result":
                        return result

                except Exception as exc:
                    await run.handle_exception(exc)

        if return_type == "state":
            return run.state
        return await run.result()


def run_sync_task(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    engine = TaskRunEngine[P, R](task=task, parameters=parameters, task_run=task_run)
    # This is a context manager that keeps track of the run of the task run.
    with engine.start_sync() as run:
        run_sync(run.begin_run())

        while run.is_running():
            with run.enter_run_context_sync():
                try:
                    # This is where the task is actually run.
                    with timeout_sync(run.task.timeout_seconds):
                        result = cast(R, task.fn(**(parameters or {})))  # type: ignore

                    # If the task run is successful, finalize it.
                    run_sync(run.handle_success(result))
                    if return_type == "result":
                        return result

                except Exception as exc:
                    run_sync(run.handle_exception(exc))

        if return_type == "state":
            return run.state
        return run_sync(run.result())


async def run_async_generator_task(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> AsyncGenerator[Union[R, State, None], None]:
    if return_type != "result":
        raise ValueError("Return type can not be specified for async generators.")
    engine = TaskRunEngine[P, R](task=task, parameters=parameters, task_run=task_run)
    # This is a context manager that keeps track of the run of the task run.
    async with engine.start() as run:
        await run.begin_run()

        while run.is_running():
            async with run.enter_run_context():
                try:
                    # This is where the task is actually run.
                    async with timeout(run.task.timeout_seconds):
                        try:
                            gen = task.fn(**(parameters or {}))
                            while True:
                                # can't use anext < 3.10
                                gen_result = await gen.__anext__()
                                # link the current state to the result for dependency tracking
                                #
                                # TODO: this could grow the task_run_result
                                # dictionary in an unbounded way, so finding a
                                # way to periodically clean it up (using
                                # weakrefs or similar) would be good
                                link_state_to_result(run.state, gen_result)
                                yield gen_result

                        except (StopAsyncIteration, GeneratorExit):
                            await run.handle_success(None)

                except Exception as exc:
                    await run.handle_exception(exc)

        # call this to raise exceptions after retries are exhausted
        await run.result()


def run_sync_generator_task(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Generator[Union[R, State, None], None, None]:
    engine = TaskRunEngine[P, R](task=task, parameters=parameters, task_run=task_run)
    # This is a context manager that keeps track of the run of the task run.
    with engine.start_sync() as run:
        run_sync(run.begin_run())

        while run.is_running():
            with run.enter_run_context_sync():
                try:
                    # This is where the task is actually run.
                    with timeout_sync(run.task.timeout_seconds):
                        try:
                            gen = task.fn(**(parameters or {}))
                            # yield in a while loop instead of `yield from` to
                            # handle StopIteration
                            while True:
                                gen_result = next(gen)
                                # link the current state to the result for dependency tracking
                                #
                                # TODO: this could grow the task_run_result
                                # dictionary in an unbounded way, so finding a
                                # way to periodically clean it up (using
                                # weakrefs or similar) would be good
                                link_state_to_result(run.state, gen_result)
                                yield gen_result

                        except (StopIteration, GeneratorExit) as exc:
                            if isinstance(exc, StopIteration):
                                result = exc.value
                            else:
                                result = None
                            run_sync(run.handle_success(result))
                            if return_type == "result":
                                return result

                except Exception as exc:
                    run_sync(run.handle_exception(exc))

        if return_type == "state":
            return run.state
        return run_sync(run.result())


def run_task(
    task: Task[P, Coroutine[Any, Any, R]],
    task_run: Optional[TaskRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    """
    Runs a task by choosing the appropriate handler based on the task's function type.
    """
    kwargs = dict(
        task=task,
        task_run=task_run,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
    )
    if inspect.isasyncgenfunction(task.fn):
        return run_async_generator_task(**kwargs)
    elif inspect.isgeneratorfunction(task.fn):
        return run_sync_generator_task(**kwargs)
    elif inspect.iscoroutinefunction(task.fn):
        return run_async_task(**kwargs)
    else:
        return run_sync_task(**kwargs)
