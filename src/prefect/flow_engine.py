import inspect
import logging
import os
import time
from contextlib import ExitStack, contextmanager
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
    Literal,
    Optional,
    Tuple,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

from typing_extensions import ParamSpec

from prefect import Task
from prefect.client.orchestration import SyncPrefectClient, get_client
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.sorting import FlowRunSort
from prefect.context import ClientContext, FlowRunContext, TagsContext
from prefect.exceptions import Abort, Pause, PrefectException, UpstreamTaskError
from prefect.flows import Flow, load_flow_from_entrypoint, load_flow_from_flow_run
from prefect.futures import PrefectFuture, resolve_futures_to_states
from prefect.logging.loggers import (
    flow_run_logger,
    get_logger,
    get_run_logger,
    patch_print,
)
from prefect.results import ResultFactory
from prefect.settings import PREFECT_DEBUG_MODE
from prefect.states import (
    Failed,
    Pending,
    Running,
    State,
    exception_to_crashed_state,
    exception_to_failed_state,
    return_value_to_state,
)
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.callables import call_with_parameters, parameters_to_args_kwargs
from prefect.utilities.collections import visit_collection
from prefect.utilities.engine import (
    _get_hook_name,
    _resolve_custom_flow_run_name,
    capture_sigterm,
    link_state_to_result,
    propose_state_sync,
    resolve_to_final_result,
)
from prefect.utilities.timeout import timeout, timeout_async
from prefect.utilities.urls import url_for

P = ParamSpec("P")
R = TypeVar("R")


def load_flow_and_flow_run(flow_run_id: UUID) -> Tuple[FlowRun, Flow]:
    ## TODO: add error handling to update state and log tracebacks
    entrypoint = os.environ.get("PREFECT__FLOW_ENTRYPOINT")

    client = cast(SyncPrefectClient, get_client(sync_client=True))

    flow_run = client.read_flow_run(flow_run_id)
    if entrypoint:
        flow = load_flow_from_entrypoint(entrypoint)
    else:
        flow = run_coro_as_sync(load_flow_from_flow_run(flow_run))

    return flow_run, flow


@dataclass
class FlowRunEngine(Generic[P, R]):
    flow: Union[Flow[P, R], Flow[P, Coroutine[Any, Any, R]]]
    parameters: Optional[Dict[str, Any]] = None
    flow_run: Optional[FlowRun] = None
    flow_run_id: Optional[UUID] = None
    logger: logging.Logger = field(default_factory=lambda: get_logger("engine"))
    wait_for: Optional[Iterable[PrefectFuture]] = None
    _is_started: bool = False
    _client: Optional[SyncPrefectClient] = None
    short_circuit: bool = False
    _flow_run_name_set: bool = False

    def __post_init__(self):
        if self.flow is None and self.flow_run_id is None:
            raise ValueError("Either a flow or a flow_run_id must be provided.")

        if self.parameters is None:
            self.parameters = {}

    @property
    def client(self) -> SyncPrefectClient:
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        return self._client

    @property
    def state(self) -> State:
        return self.flow_run.state  # type: ignore

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
            context={},
        )

    def begin_run(self) -> State:
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
            return state

        # validate prior to context so that context receives validated params
        if self.flow.should_validate_parameters:
            try:
                self.parameters = self.flow.validate_parameters(self.parameters or {})
            except Exception as exc:
                message = "Validation of flow parameters failed with error:"
                self.logger.error("%s %s", message, exc)
                self.handle_exception(
                    exc,
                    msg=message,
                    result_factory=run_coro_as_sync(ResultFactory.from_flow(self.flow)),
                )
                self.short_circuit = True

        new_state = Running()
        state = self.set_state(new_state)
        while state.is_pending():
            time.sleep(0.2)
            state = self.set_state(new_state)
        return state

    def set_state(self, state: State, force: bool = False) -> State:
        """ """
        # prevents any state-setting activity
        if self.short_circuit:
            return self.state

        state = propose_state_sync(
            self.client, state, flow_run_id=self.flow_run.id, force=force
        )  # type: ignore
        self.flow_run.state = state  # type: ignore
        self.flow_run.state_name = state.name  # type: ignore
        self.flow_run.state_type = state.type  # type: ignore
        return state

    def result(self, raise_on_failure: bool = True) -> "Union[R, State, None]":
        _result = self.state.result(raise_on_failure=raise_on_failure, fetch=True)  # type: ignore
        # state.result is a `sync_compatible` function that may or may not return an awaitable
        # depending on whether the parent frame is sync or not
        if inspect.isawaitable(_result):
            _result = run_coro_as_sync(_result)
        return _result

    def handle_success(self, result: R) -> R:
        result_factory = getattr(FlowRunContext.get(), "result_factory", None)
        if result_factory is None:
            raise ValueError("Result factory is not set")
        terminal_state = run_coro_as_sync(
            return_value_to_state(
                resolve_futures_to_states(result),
                result_factory=result_factory,
            )
        )
        self.set_state(terminal_state)
        return result

    def handle_exception(
        self,
        exc: Exception,
        msg: Optional[str] = None,
        result_factory: Optional[ResultFactory] = None,
    ) -> State:
        context = FlowRunContext.get()
        terminal_state = run_coro_as_sync(
            exception_to_failed_state(
                exc,
                message=msg or "Flow run encountered an exception:",
                result_factory=result_factory
                or getattr(context, "result_factory", None),
            )
        )
        state = self.set_state(terminal_state)
        if self.state.is_scheduled():
            self.logger.info(
                (
                    f"Received non-final state {state.name!r} when proposing final"
                    f" state {terminal_state.name!r} and will attempt to run again..."
                ),
            )
            state = self.set_state(Running())
        return state

    def handle_timeout(self, exc: TimeoutError) -> None:
        message = f"Flow run exceeded timeout of {self.flow.timeout_seconds} seconds"
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

    def load_subflow_run(
        self,
        parent_task_run: TaskRun,
        client: SyncPrefectClient,
        context: FlowRunContext,
    ) -> Union[FlowRun, None]:
        """
        This method attempts to load an existing flow run for a subflow task
        run, if appropriate.

        If the parent task run is in a final but not COMPLETED state, and not
        being rerun, then we attempt to load an existing flow run instead of
        creating a new one. This will prevent the engine from running the
        subflow again.

        If no existing flow run is found, or if the subflow should be rerun,
        then no flow run is returned.
        """

        # check if the parent flow run is rerunning
        rerunning = (
            context.flow_run.run_count > 1
            if getattr(context, "flow_run", None)
            and isinstance(context.flow_run, FlowRun)
            else False
        )

        # if the parent task run is in a final but not completed state, and
        # not rerunning, then retrieve the most recent flow run instead of
        # creating a new one. This effectively loads a cached flow run for
        # situations where we are confident the flow should not be run
        # again.
        assert isinstance(parent_task_run.state, State)
        if parent_task_run.state.is_final() and not (
            rerunning and not parent_task_run.state.is_completed()
        ):
            # return the most recent flow run, if it exists
            flow_runs = client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    parent_task_run_id={"any_": [parent_task_run.id]}
                ),
                sort=FlowRunSort.EXPECTED_START_TIME_ASC,
                limit=1,
            )
            if flow_runs:
                return flow_runs[-1]

    def create_flow_run(self, client: SyncPrefectClient) -> FlowRun:
        flow_run_ctx = FlowRunContext.get()
        parameters = self.parameters or {}

        parent_task_run = None

        # this is a subflow run
        if flow_run_ctx:
            # add a task to a parent flow run that represents the execution of a subflow run
            parent_task = Task(
                name=self.flow.name, fn=self.flow.fn, version=self.flow.version
            )

            parent_task_run = run_coro_as_sync(
                parent_task.create_run(
                    flow_run_context=flow_run_ctx,
                    parameters=self.parameters,
                    wait_for=self.wait_for,
                )
            )

            # check if there is already a flow run for this subflow
            if subflow_run := self.load_subflow_run(
                parent_task_run=parent_task_run, client=client, context=flow_run_ctx
            ):
                return subflow_run

        flow_run = client.create_flow_run(
            flow=self.flow,
            parameters=self.flow.serialize_parameters(parameters),
            state=Pending(),
            parent_task_run_id=getattr(parent_task_run, "id", None),
            tags=TagsContext.get().current_tags,
        )
        if flow_run_ctx:
            parent_logger = get_run_logger(flow_run_ctx)
            parent_logger.info(
                f"Created subflow run {flow_run.name!r} for flow {self.flow.name!r}"
            )
        else:
            self.logger.info(
                f"Created flow run {flow_run.name!r} for flow {self.flow.name!r}"
            )

        return flow_run

    def call_hooks(self, state: State = None) -> Iterable[Callable]:
        if state is None:
            state = self.state
        flow = self.flow
        flow_run = self.flow_run

        if not flow_run:
            raise ValueError("Flow run is not set")

        enable_cancellation_and_crashed_hooks = (
            os.environ.get(
                "PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS", "true"
            ).lower()
            == "true"
        )

        if state.is_failed() and flow.on_failure_hooks:
            hooks = flow.on_failure_hooks
        elif state.is_completed() and flow.on_completion_hooks:
            hooks = flow.on_completion_hooks
        elif (
            enable_cancellation_and_crashed_hooks
            and state.is_cancelling()
            and flow.on_cancellation_hooks
        ):
            hooks = flow.on_cancellation_hooks
        elif (
            enable_cancellation_and_crashed_hooks
            and state.is_crashed()
            and flow.on_crashed_hooks
        ):
            hooks = flow.on_crashed_hooks
        elif state.is_running() and flow.on_running_hooks:
            hooks = flow.on_running_hooks
        else:
            hooks = None

        for hook in hooks or []:
            hook_name = _get_hook_name(hook)

            try:
                self.logger.info(
                    f"Running hook {hook_name!r} in response to entering state"
                    f" {state.name!r}"
                )
                result = hook(flow, flow_run, state)
                if inspect.isawaitable(result):
                    run_coro_as_sync(result)
            except Exception:
                self.logger.error(
                    f"An error was encountered while running hook {hook_name!r}",
                    exc_info=True,
                )
            else:
                self.logger.info(f"Hook {hook_name!r} finished running successfully")

    @contextmanager
    def setup_run_context(self, client: Optional[SyncPrefectClient] = None):
        from prefect.utilities.engine import (
            should_log_prints,
        )

        if client is None:
            client = self.client
        if not self.flow_run:
            raise ValueError("Flow run not set")

        self.flow_run = client.read_flow_run(self.flow_run.id)
        log_prints = should_log_prints(self.flow)

        with ExitStack() as stack:
            # TODO: Explore closing task runner before completing the flow to
            # wait for futures to complete
            stack.enter_context(capture_sigterm())
            if log_prints:
                stack.enter_context(patch_print())
            task_runner = stack.enter_context(self.flow.task_runner.duplicate())
            stack.enter_context(
                FlowRunContext(
                    flow=self.flow,
                    log_prints=log_prints,
                    flow_run=self.flow_run,
                    parameters=self.parameters,
                    client=client,
                    result_factory=run_coro_as_sync(ResultFactory.from_flow(self.flow)),
                    task_runner=task_runner,
                )
            )
            # set the logger to the flow run logger
            self.logger = flow_run_logger(flow_run=self.flow_run, flow=self.flow)

            # update the flow run name if necessary
            if not self._flow_run_name_set and self.flow.flow_run_name:
                flow_run_name = _resolve_custom_flow_run_name(
                    flow=self.flow, parameters=self.parameters
                )
                self.client.set_flow_run_name(
                    flow_run_id=self.flow_run.id, name=flow_run_name
                )
                self.logger.extra["flow_run_name"] = flow_run_name
                self.logger.debug(
                    f"Renamed flow run {self.flow_run.name!r} to {flow_run_name!r}"
                )
                self.flow_run.name = flow_run_name
                self._flow_run_name_set = True
            yield

    @contextmanager
    def initialize_run(self):
        """
        Enters a client context and creates a flow run if needed.
        """
        with ClientContext.get_or_create() as client_ctx:
            self._client = client_ctx.sync_client
            self._is_started = True

            if not self.flow_run:
                self.flow_run = self.create_flow_run(self.client)
                flow_run_url = url_for(self.flow_run)

                if flow_run_url:
                    self.logger.info(
                        f"View at {flow_run_url}", extra={"send_to_api": False}
                    )
            else:
                # Update the empirical policy to match the flow if it is not set
                if self.flow_run.empirical_policy.retry_delay is None:
                    self.flow_run.empirical_policy.retry_delay = (
                        self.flow.retry_delay_seconds
                    )

                if self.flow_run.empirical_policy.retries is None:
                    self.flow_run.empirical_policy.retries = self.flow.retries

                self.client.update_flow_run(
                    flow_run_id=self.flow_run.id,
                    flow_version=self.flow.version,
                    empirical_policy=self.flow_run.empirical_policy,
                )
            try:
                yield self
            except Exception:
                # regular exceptions are caught and re-raised to the user
                raise
            except (Abort, Pause):
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
                self.logger.log(
                    level=logging.INFO if self.state.is_completed() else logging.ERROR,
                    msg=f"Finished in state {display_state}",
                )

                self._is_started = False
                self._client = None

    def is_running(self) -> bool:
        if getattr(self, "flow_run", None) is None:
            return False
        return getattr(self, "flow_run").state.is_running()

    def is_pending(self) -> bool:
        if getattr(self, "flow_run", None) is None:
            return False  # TODO: handle this differently?
        return getattr(self, "flow_run").state.is_pending()

    # --------------------------
    #
    # The following methods compose the main task run loop
    #
    # --------------------------

    @contextmanager
    def start(self) -> Generator[None, None, None]:
        with self.initialize_run():
            self.begin_run()

            if self.state.is_running():
                self.call_hooks()
            try:
                yield
            finally:
                if self.state.is_final() or self.state.is_cancelling():
                    self.call_hooks()

    @contextmanager
    def run_context(self):
        timeout_context = timeout_async if self.flow.isasync else timeout
        # reenter the run context to ensure it is up to date for every run
        with self.setup_run_context():
            try:
                with timeout_context(seconds=self.flow.timeout_seconds):
                    self.logger.debug(
                        f"Executing flow {self.flow.name!r} for flow run {self.flow_run.name!r}..."
                    )
                    yield self
            except TimeoutError as exc:
                self.handle_timeout(exc)
            except Exception as exc:
                self.logger.exception(f"Encountered exception during execution: {exc}")
                self.handle_exception(exc)

    def call_flow_fn(self) -> Union[R, Coroutine[Any, Any, R]]:
        """
        Convenience method to call the flow function. Returns a coroutine if the
        flow is async.
        """
        if self.flow.isasync:

            async def _call_flow_fn():
                result = await call_with_parameters(self.flow.fn, self.parameters)
                self.handle_success(result)

            return _call_flow_fn()
        else:
            result = call_with_parameters(self.flow.fn, self.parameters)
            self.handle_success(result)


def run_flow_sync(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    parameters = flow_run.parameters if flow_run else parameters

    engine = FlowRunEngine[P, R](
        flow=flow, parameters=parameters, flow_run=flow_run, wait_for=wait_for
    )

    with engine.start():
        while engine.is_running():
            with engine.run_context():
                engine.call_flow_fn()

    return engine.state if return_type == "state" else engine.result()


async def run_flow_async(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    parameters = flow_run.parameters if flow_run else parameters

    engine = FlowRunEngine[P, R](
        flow=flow, parameters=parameters, flow_run=flow_run, wait_for=wait_for
    )

    with engine.start():
        while engine.is_running():
            with engine.run_context():
                await engine.call_flow_fn()

    return engine.state if return_type == "state" else engine.result()


def run_generator_flow_sync(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Generator[R, None, None]:
    if return_type != "result":
        raise ValueError("The return_type for a generator flow must be 'result'")

    engine = FlowRunEngine[P, R](
        flow=flow, parameters=parameters, flow_run=flow_run, wait_for=wait_for
    )

    with engine.start():
        while engine.is_running():
            with engine.run_context():
                call_args, call_kwargs = parameters_to_args_kwargs(
                    flow.fn, engine.parameters or {}
                )
                gen = flow.fn(*call_args, **call_kwargs)
                try:
                    while True:
                        gen_result = next(gen)
                        # link the current state to the result for dependency tracking
                        link_state_to_result(engine.state, gen_result)
                        yield gen_result
                except StopIteration as exc:
                    engine.handle_success(exc.value)
                except GeneratorExit as exc:
                    engine.handle_success(None)
                    gen.throw(exc)

    return engine.result()


async def run_generator_flow_async(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
) -> AsyncGenerator[R, None]:
    if return_type != "result":
        raise ValueError("The return_type for a generator flow must be 'result'")

    engine = FlowRunEngine[P, R](
        flow=flow, parameters=parameters, flow_run=flow_run, wait_for=wait_for
    )

    with engine.start():
        while engine.is_running():
            with engine.run_context():
                call_args, call_kwargs = parameters_to_args_kwargs(
                    flow.fn, engine.parameters or {}
                )
                gen = flow.fn(*call_args, **call_kwargs)
                try:
                    while True:
                        # can't use anext in Python < 3.10
                        gen_result = await gen.__anext__()
                        # link the current state to the result for dependency tracking
                        link_state_to_result(engine.state, gen_result)
                        yield gen_result
                except (StopAsyncIteration, GeneratorExit) as exc:
                    engine.handle_success(None)
                    if isinstance(exc, GeneratorExit):
                        gen.throw(exc)

    # async generators can't return, but we can raise failures here
    if engine.state.is_failed():
        engine.result()


def run_flow(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    kwargs = dict(
        flow=flow,
        flow_run=flow_run,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
    )
    if flow.isasync and flow.isgenerator:
        return run_generator_flow_async(**kwargs)
    elif flow.isgenerator:
        return run_generator_flow_sync(**kwargs)
    elif flow.isasync:
        return run_flow_async(**kwargs)
    else:
        return run_flow_sync(**kwargs)
