from __future__ import annotations

import asyncio
import logging
import multiprocessing
import multiprocessing.context
import os
import time
from contextlib import (
    AsyncExitStack,
    ExitStack,
    asynccontextmanager,
    contextmanager,
    nullcontext,
)
from dataclasses import dataclass, field
from functools import wraps
from typing import (
    Any,
    AsyncGenerator,
    Coroutine,
    Dict,
    Generator,
    Generic,
    Iterable,
    Literal,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

from anyio import CancelScope
from opentelemetry import propagate, trace
from typing_extensions import ParamSpec

from prefect import Task
from prefect.client.orchestration import PrefectClient, SyncPrefectClient, get_client
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.sorting import FlowRunSort
from prefect.concurrency.asyncio import (
    amaintain_concurrency_lease,
)
from prefect.concurrency.context import ConcurrencyContext
from prefect.concurrency.sync import maintain_concurrency_lease
from prefect.concurrency.v1.context import ConcurrencyContext as ConcurrencyContextV1
from prefect.context import (
    AsyncClientContext,
    FlowRunContext,
    SettingsContext,
    SyncClientContext,
    TagsContext,
    get_settings_context,
    hydrated_context,
    serialize_context,
)
from prefect.engine import handle_engine_signals
from prefect.exceptions import (
    Abort,
    MissingFlowError,
    Pause,
    PrefectException,
    TerminationSignal,
    UpstreamTaskError,
)
from prefect.flows import (
    Flow,
    load_flow_from_entrypoint,
    load_flow_from_flow_run,
    load_function_and_convert_to_flow,
)
from prefect.futures import PrefectFuture, resolve_futures_to_states
from prefect.logging.loggers import (
    flow_run_logger,
    get_logger,
    get_run_logger,
    patch_print,
)
from prefect.results import (
    ResultStore,
    get_result_store,
    should_persist_result,
)
from prefect.settings import PREFECT_DEBUG_MODE
from prefect.settings.context import get_current_settings
from prefect.settings.models.root import Settings
from prefect.states import (
    Failed,
    Pending,
    Running,
    State,
    exception_to_crashed_state,
    exception_to_failed_state,
    return_value_to_state,
)
from prefect.telemetry.run_telemetry import (
    LABELS_TRACEPARENT_KEY,
    TRACEPARENT_KEY,
    OTELSetter,
    RunTelemetry,
)
from prefect.types import KeyValueLabels
from prefect.utilities._engine import get_hook_name, resolve_custom_flow_run_name
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.callables import (
    call_with_parameters,
    cloudpickle_wrapped_call,
    get_call_parameters,
    parameters_to_args_kwargs,
)
from prefect.utilities.collections import visit_collection
from prefect.utilities.engine import (
    capture_sigterm,
    link_state_to_flow_run_result,
    propose_state,
    propose_state_sync,
    resolve_to_final_result,
)
from prefect.utilities.timeout import timeout, timeout_async
from prefect.utilities.urls import url_for

P = ParamSpec("P")
R = TypeVar("R")


class FlowRunTimeoutError(TimeoutError):
    """Raised when a flow run exceeds its defined timeout."""


def load_flow_run(flow_run_id: UUID) -> FlowRun:
    client = get_client(sync_client=True)
    flow_run = client.read_flow_run(flow_run_id)
    return flow_run


def load_flow(flow_run: FlowRun) -> Flow[..., Any]:
    entrypoint = os.environ.get("PREFECT__FLOW_ENTRYPOINT")

    if entrypoint:
        # we should not accept a placeholder flow at runtime
        try:
            flow = load_flow_from_entrypoint(entrypoint, use_placeholder_flow=False)
        except MissingFlowError:
            flow = load_function_and_convert_to_flow(entrypoint)
    else:
        flow = run_coro_as_sync(
            load_flow_from_flow_run(flow_run, use_placeholder_flow=False)
        )
    return flow


def load_flow_and_flow_run(flow_run_id: UUID) -> tuple[FlowRun, Flow[..., Any]]:
    flow_run = load_flow_run(flow_run_id)
    flow = load_flow(flow_run)
    return flow_run, flow


@dataclass
class BaseFlowRunEngine(Generic[P, R]):
    flow: Union[Flow[P, R], Flow[P, Coroutine[Any, Any, R]]]
    parameters: Optional[Dict[str, Any]] = None
    flow_run: Optional[FlowRun] = None
    flow_run_id: Optional[UUID] = None
    logger: logging.Logger = field(default_factory=lambda: get_logger("engine"))
    wait_for: Optional[Iterable[PrefectFuture[Any]]] = None
    context: Optional[dict[str, Any]] = None
    # holds the return value from the user code
    _return_value: Union[R, Type[NotSet]] = NotSet
    # holds the exception raised by the user code, if any
    _raised: Union[Exception, Type[NotSet]] = NotSet
    _is_started: bool = False
    short_circuit: bool = False
    _flow_run_name_set: bool = False
    _telemetry: RunTelemetry = field(default_factory=RunTelemetry)

    def __post_init__(self) -> None:
        if self.flow is None and self.flow_run_id is None:
            raise ValueError("Either a flow or a flow_run_id must be provided.")

        if self.parameters is None:
            self.parameters = {}

    @property
    def state(self) -> State:
        return self.flow_run.state  # type: ignore

    def is_running(self) -> bool:
        if getattr(self, "flow_run", None) is None:
            return False
        return getattr(self, "flow_run").state.is_running()

    def is_pending(self) -> bool:
        if getattr(self, "flow_run", None) is None:
            return False  # TODO: handle this differently?
        return getattr(self, "flow_run").state.is_pending()

    def cancel_all_tasks(self) -> None:
        if hasattr(self.flow.task_runner, "cancel_all"):
            self.flow.task_runner.cancel_all()  # type: ignore

    def _update_otel_labels(
        self, span: trace.Span, client: Union[SyncPrefectClient, PrefectClient]
    ):
        parent_flow_run_ctx = FlowRunContext.get()

        if parent_flow_run_ctx and parent_flow_run_ctx.flow_run:
            if traceparent := parent_flow_run_ctx.flow_run.labels.get(
                LABELS_TRACEPARENT_KEY
            ):
                carrier: KeyValueLabels = {TRACEPARENT_KEY: traceparent}
                propagate.get_global_textmap().inject(
                    carrier={TRACEPARENT_KEY: traceparent},
                    setter=OTELSetter(),
                )

            else:
                carrier: KeyValueLabels = {}
                propagate.get_global_textmap().inject(
                    carrier,
                    context=trace.set_span_in_context(span),
                    setter=OTELSetter(),
                )
            if carrier.get(TRACEPARENT_KEY):
                if self.flow_run:
                    client.update_flow_run_labels(
                        flow_run_id=self.flow_run.id,
                        labels={LABELS_TRACEPARENT_KEY: carrier[TRACEPARENT_KEY]},
                    )
                else:
                    self.logger.info(
                        f"Tried to set traceparent {carrier[TRACEPARENT_KEY]} for flow run, but None was found"
                    )


@dataclass
class FlowRunEngine(BaseFlowRunEngine[P, R]):
    _client: Optional[SyncPrefectClient] = None
    flow_run: FlowRun | None = None
    parameters: dict[str, Any] | None = None

    @property
    def client(self) -> SyncPrefectClient:
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        return self._client

    def _resolve_parameters(self):
        if not self.parameters:
            return

        resolved_parameters = {}
        for parameter, value in self.parameters.items():
            try:
                resolved_parameters[parameter] = visit_collection(
                    value,
                    visit_fn=resolve_to_final_result,
                    return_data=True,
                    max_depth=-1,
                    remove_annotations=True,
                    context={"parameter_name": parameter},
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
                    result_store=get_result_store().update_for_flow(
                        self.flow, _sync=True
                    ),
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

        self._telemetry.update_state(state)
        self.call_hooks(state)
        return state

    def result(self, raise_on_failure: bool = True) -> "Union[R, State, None]":
        if self._return_value is not NotSet and not isinstance(
            self._return_value, State
        ):
            _result = self._return_value
            link_state_to_flow_run_result(self.state, _result)

            if asyncio.iscoroutine(_result):
                # getting the value for a BaseResult may return an awaitable
                # depending on whether the parent frame is sync or not
                _result = run_coro_as_sync(_result)
            return _result

        if self._raised is not NotSet:
            if raise_on_failure:
                raise self._raised
            return self._raised

        # This is a fall through case which leans on the existing state result mechanics to get the
        # return value. This is necessary because we currently will return a State object if the
        # the State was Prefect-created.
        # TODO: Remove the need to get the result from a State except in cases where the return value
        # is a State object.
        _result = self.state.result(raise_on_failure=raise_on_failure, _sync=True)  # type: ignore
        return _result

    def handle_success(self, result: R) -> R:
        result_store = getattr(FlowRunContext.get(), "result_store", None)
        if result_store is None:
            raise ValueError("Result store is not set")
        resolved_result = resolve_futures_to_states(result)
        terminal_state = run_coro_as_sync(
            return_value_to_state(
                resolved_result,
                result_store=result_store,
                write_result=should_persist_result(),
            )
        )
        self.set_state(terminal_state)
        self._return_value = resolved_result

        link_state_to_flow_run_result(terminal_state, resolved_result)
        self._telemetry.end_span_on_success()

        return result

    def handle_exception(
        self,
        exc: Exception,
        msg: Optional[str] = None,
        result_store: Optional[ResultStore] = None,
    ) -> State:
        context = FlowRunContext.get()
        terminal_state = cast(
            State,
            run_coro_as_sync(
                exception_to_failed_state(
                    exc,
                    message=msg or "Flow run encountered an exception:",
                    result_store=result_store or getattr(context, "result_store", None),
                    write_result=True,
                )
            ),
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
        self._raised = exc
        self._telemetry.record_exception(exc)
        self._telemetry.end_span_on_failure(state.message)

        return state

    def handle_timeout(self, exc: TimeoutError) -> None:
        if isinstance(exc, FlowRunTimeoutError):
            message = (
                f"Flow run exceeded timeout of {self.flow.timeout_seconds} second(s)"
            )
        else:
            message = f"Flow run failed due to timeout: {exc!r}"
        self.logger.error(message)
        state = Failed(
            data=exc,
            message=message,
            name="TimedOut",
        )
        self.set_state(state)
        self._raised = exc
        self._telemetry.record_exception(exc)
        self._telemetry.end_span_on_failure(message)

    def handle_crash(self, exc: BaseException) -> None:
        state = run_coro_as_sync(exception_to_crashed_state(exc))
        self.logger.error(f"Crash detected! {state.message}")
        self.logger.debug("Crash details:", exc_info=exc)
        self.set_state(state, force=True)
        self._raised = exc
        self._telemetry.record_exception(exc)
        self._telemetry.end_span_on_failure(state.message if state else None)

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
                loaded_flow_run = flow_runs[-1]
                self._return_value = loaded_flow_run.state
                return loaded_flow_run

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

        return client.create_flow_run(
            flow=self.flow,
            parameters=self.flow.serialize_parameters(parameters),
            state=Pending(),
            parent_task_run_id=getattr(parent_task_run, "id", None),
            tags=TagsContext.get().current_tags,
        )

    def call_hooks(self, state: Optional[State] = None) -> None:
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
            hook_name = get_hook_name(hook)

            try:
                self.logger.info(
                    f"Running hook {hook_name!r} in response to entering state"
                    f" {state.name!r}"
                )
                result = hook(flow, flow_run, state)
                if asyncio.iscoroutine(result):
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
                    result_store=get_result_store().update_for_flow(
                        self.flow, _sync=True
                    ),
                    task_runner=task_runner,
                    persist_result=self.flow.persist_result
                    if self.flow.persist_result is not None
                    else should_persist_result(),
                )
            )
            stack.enter_context(ConcurrencyContextV1())
            stack.enter_context(ConcurrencyContext())
            if lease_id := self.state.state_details.deployment_concurrency_lease_id:
                stack.enter_context(
                    maintain_concurrency_lease(
                        lease_id, 300, raise_on_lease_renewal_failure=True
                    )
                )

            # set the logger to the flow run logger

            self.logger: "logging.Logger" = flow_run_logger(
                flow_run=self.flow_run, flow=self.flow
            )  # type: ignore

            # update the flow run name if necessary
            if not self._flow_run_name_set and self.flow.flow_run_name:
                flow_run_name = resolve_custom_flow_run_name(
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

                self._telemetry.update_run_name(name=flow_run_name)

            if self.flow_run.parent_task_run_id:
                _logger = get_run_logger(FlowRunContext.get())
                run_type = "subflow"
            else:
                _logger = self.logger
                run_type = "flow"

            _logger.info(
                f"Beginning {run_type} run {self.flow_run.name!r} for flow {self.flow.name!r}"
            )

            if flow_run_url := url_for(self.flow_run):
                self.logger.info(
                    f"View at {flow_run_url}", extra={"send_to_api": False}
                )

            yield

    @contextmanager
    def initialize_run(self):
        """
        Enters a client context and creates a flow run if needed.
        """
        with hydrated_context(self.context):
            with SyncClientContext.get_or_create() as client_ctx:
                self._client = client_ctx.client
                self._is_started = True

                if not self.flow_run:
                    self.flow_run = self.create_flow_run(self.client)
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

                self._telemetry.start_span(
                    run=self.flow_run,
                    client=self.client,
                    parameters=self.parameters,
                )

                try:
                    yield self

                except TerminationSignal as exc:
                    self.cancel_all_tasks()
                    self.handle_crash(exc)
                    raise
                except Exception:
                    # regular exceptions are caught and re-raised to the user
                    raise
                except (Abort, Pause) as exc:
                    if getattr(exc, "state", None):
                        # we set attribute explicitly because
                        # internals will have already called the state change API
                        self.flow_run.state = exc.state
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
                        level=logging.INFO,
                        msg=f"Finished in state {display_state}",
                    )

                    self._is_started = False
                    self._client = None

    # --------------------------
    #
    # The following methods compose the main task run loop
    #
    # --------------------------

    @contextmanager
    def start(self) -> Generator[None, None, None]:
        with self.initialize_run():
            with (
                trace.use_span(self._telemetry.span)
                if self._telemetry.span
                else nullcontext()
            ):
                self.begin_run()

                yield

    @contextmanager
    def run_context(self):
        timeout_context = timeout_async if self.flow.isasync else timeout
        # reenter the run context to ensure it is up to date for every run
        with self.setup_run_context():
            try:
                with timeout_context(
                    seconds=self.flow.timeout_seconds,
                    timeout_exc_type=FlowRunTimeoutError,
                ):
                    self.logger.debug(
                        f"Executing flow {self.flow.name!r} for flow run {self.flow_run.name!r}..."
                    )
                    yield self
            except TimeoutError as exc:
                self.handle_timeout(exc)
            except Exception as exc:
                self.logger.exception("Encountered exception during execution: %r", exc)
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


@dataclass
class AsyncFlowRunEngine(BaseFlowRunEngine[P, R]):
    """
    Async version of the flow run engine.

    NOTE: This has not been fully asyncified yet which may lead to async flows
    not being fully asyncified.
    """

    _client: Optional[PrefectClient] = None
    parameters: dict[str, Any] | None = None
    flow_run: FlowRun | None = None

    @property
    def client(self) -> PrefectClient:
        if not self._is_started or self._client is None:
            raise RuntimeError("Engine has not started.")
        return self._client

    def _resolve_parameters(self):
        if not self.parameters:
            return

        resolved_parameters = {}
        for parameter, value in self.parameters.items():
            try:
                resolved_parameters[parameter] = visit_collection(
                    value,
                    visit_fn=resolve_to_final_result,
                    return_data=True,
                    max_depth=-1,
                    remove_annotations=True,
                    context={"parameter_name": parameter},
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

    async def begin_run(self) -> State:
        try:
            self._resolve_parameters()
            self._wait_for_dependencies()
        except UpstreamTaskError as upstream_exc:
            state = await self.set_state(
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
                await self.handle_exception(
                    exc,
                    msg=message,
                    result_store=get_result_store().update_for_flow(
                        self.flow, _sync=True
                    ),
                )
                self.short_circuit = True

        new_state = Running()
        state = await self.set_state(new_state)
        while state.is_pending():
            await asyncio.sleep(0.2)
            state = await self.set_state(new_state)
        return state

    async def set_state(self, state: State, force: bool = False) -> State:
        """ """
        # prevents any state-setting activity
        if self.short_circuit:
            return self.state

        state = await propose_state(
            self.client, state, flow_run_id=self.flow_run.id, force=force
        )  # type: ignore
        self.flow_run.state = state  # type: ignore
        self.flow_run.state_name = state.name  # type: ignore
        self.flow_run.state_type = state.type  # type: ignore

        self._telemetry.update_state(state)
        await self.call_hooks(state)
        return state

    async def result(self, raise_on_failure: bool = True) -> "Union[R, State, None]":
        if self._return_value is not NotSet and not isinstance(
            self._return_value, State
        ):
            _result = self._return_value
            link_state_to_flow_run_result(self.state, _result)

            if asyncio.iscoroutine(_result):
                # getting the value for a BaseResult may return an awaitable
                # depending on whether the parent frame is sync or not
                _result = await _result
            return _result

        if self._raised is not NotSet:
            if raise_on_failure:
                raise self._raised
            return self._raised

        # This is a fall through case which leans on the existing state result mechanics to get the
        # return value. This is necessary because we currently will return a State object if the
        # the State was Prefect-created.
        # TODO: Remove the need to get the result from a State except in cases where the return value
        # is a State object.
        return await self.state.aresult(raise_on_failure=raise_on_failure)  # type: ignore

    async def handle_success(self, result: R) -> R:
        result_store = getattr(FlowRunContext.get(), "result_store", None)
        if result_store is None:
            raise ValueError("Result store is not set")
        resolved_result = resolve_futures_to_states(result)
        terminal_state = await return_value_to_state(
            resolved_result,
            result_store=result_store,
            write_result=should_persist_result(),
        )
        await self.set_state(terminal_state)
        self._return_value = resolved_result

        self._telemetry.end_span_on_success()

        return result

    async def handle_exception(
        self,
        exc: Exception,
        msg: Optional[str] = None,
        result_store: Optional[ResultStore] = None,
    ) -> State:
        context = FlowRunContext.get()
        terminal_state = cast(
            State,
            await exception_to_failed_state(
                exc,
                message=msg or "Flow run encountered an exception:",
                result_store=result_store or getattr(context, "result_store", None),
                write_result=True,
            ),
        )
        state = await self.set_state(terminal_state)
        if self.state.is_scheduled():
            self.logger.info(
                (
                    f"Received non-final state {state.name!r} when proposing final"
                    f" state {terminal_state.name!r} and will attempt to run again..."
                ),
            )
            state = await self.set_state(Running())
        self._raised = exc
        self._telemetry.record_exception(exc)
        self._telemetry.end_span_on_failure(state.message)

        return state

    async def handle_timeout(self, exc: TimeoutError) -> None:
        if isinstance(exc, FlowRunTimeoutError):
            message = (
                f"Flow run exceeded timeout of {self.flow.timeout_seconds} second(s)"
            )
        else:
            message = f"Flow run failed due to timeout: {exc!r}"
        self.logger.error(message)
        state = Failed(
            data=exc,
            message=message,
            name="TimedOut",
        )
        await self.set_state(state)
        self._raised = exc

        self._telemetry.record_exception(exc)
        self._telemetry.end_span_on_failure(message)

    async def handle_crash(self, exc: BaseException) -> None:
        # need to shield from asyncio cancellation to ensure we update the state
        # on the server before exiting
        with CancelScope(shield=True):
            state = await exception_to_crashed_state(exc)
            self.logger.error(f"Crash detected! {state.message}")
            self.logger.debug("Crash details:", exc_info=exc)
            await self.set_state(state, force=True)
            self._raised = exc

            self._telemetry.record_exception(exc)
            self._telemetry.end_span_on_failure(state.message)

    async def load_subflow_run(
        self,
        parent_task_run: TaskRun,
        client: PrefectClient,
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
            flow_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    parent_task_run_id={"any_": [parent_task_run.id]}
                ),
                sort=FlowRunSort.EXPECTED_START_TIME_ASC,
                limit=1,
            )
            if flow_runs:
                loaded_flow_run = flow_runs[-1]
                self._return_value = loaded_flow_run.state
                return loaded_flow_run

    async def create_flow_run(self, client: PrefectClient) -> FlowRun:
        flow_run_ctx = FlowRunContext.get()
        parameters = self.parameters or {}

        parent_task_run = None

        # this is a subflow run
        if flow_run_ctx:
            # add a task to a parent flow run that represents the execution of a subflow run
            parent_task = Task(
                name=self.flow.name, fn=self.flow.fn, version=self.flow.version
            )

            parent_task_run = await parent_task.create_run(
                flow_run_context=flow_run_ctx,
                parameters=self.parameters,
                wait_for=self.wait_for,
            )

            # check if there is already a flow run for this subflow
            if subflow_run := await self.load_subflow_run(
                parent_task_run=parent_task_run, client=client, context=flow_run_ctx
            ):
                return subflow_run

        return await client.create_flow_run(
            flow=self.flow,
            parameters=self.flow.serialize_parameters(parameters),
            state=Pending(),
            parent_task_run_id=getattr(parent_task_run, "id", None),
            tags=TagsContext.get().current_tags,
        )

    async def call_hooks(self, state: Optional[State] = None) -> None:
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
            hook_name = get_hook_name(hook)

            try:
                self.logger.info(
                    f"Running hook {hook_name!r} in response to entering state"
                    f" {state.name!r}"
                )
                result = hook(flow, flow_run, state)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                self.logger.error(
                    f"An error was encountered while running hook {hook_name!r}",
                    exc_info=True,
                )
            else:
                self.logger.info(f"Hook {hook_name!r} finished running successfully")

    @asynccontextmanager
    async def setup_run_context(self, client: Optional[PrefectClient] = None):
        from prefect.utilities.engine import (
            should_log_prints,
        )

        if client is None:
            client = self.client
        if not self.flow_run:
            raise ValueError("Flow run not set")

        self.flow_run = await client.read_flow_run(self.flow_run.id)
        log_prints = should_log_prints(self.flow)

        async with AsyncExitStack() as stack:
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
                    result_store=get_result_store().update_for_flow(
                        self.flow, _sync=True
                    ),
                    task_runner=task_runner,
                    persist_result=self.flow.persist_result
                    if self.flow.persist_result is not None
                    else should_persist_result(),
                )
            )
            stack.enter_context(ConcurrencyContextV1())
            stack.enter_context(ConcurrencyContext())
            if lease_id := self.state.state_details.deployment_concurrency_lease_id:
                await stack.enter_async_context(
                    amaintain_concurrency_lease(
                        lease_id, 300, raise_on_lease_renewal_failure=True
                    )
                )

            # set the logger to the flow run logger
            self.logger: "logging.Logger" = flow_run_logger(
                flow_run=self.flow_run, flow=self.flow
            )

            # update the flow run name if necessary

            if not self._flow_run_name_set and self.flow.flow_run_name:
                flow_run_name = resolve_custom_flow_run_name(
                    flow=self.flow, parameters=self.parameters
                )
                await self.client.set_flow_run_name(
                    flow_run_id=self.flow_run.id, name=flow_run_name
                )
                self.logger.extra["flow_run_name"] = flow_run_name
                self.logger.debug(
                    f"Renamed flow run {self.flow_run.name!r} to {flow_run_name!r}"
                )
                self.flow_run.name = flow_run_name
                self._flow_run_name_set = True

                self._telemetry.update_run_name(name=flow_run_name)
            if self.flow_run.parent_task_run_id:
                _logger = get_run_logger(FlowRunContext.get())
                run_type = "subflow"
            else:
                _logger = self.logger
                run_type = "flow"

            _logger.info(
                f"Beginning {run_type} run {self.flow_run.name!r} for flow {self.flow.name!r}"
            )

            if flow_run_url := url_for(self.flow_run):
                self.logger.info(
                    f"View at {flow_run_url}", extra={"send_to_api": False}
                )

            yield

    @asynccontextmanager
    async def initialize_run(self):
        """
        Enters a client context and creates a flow run if needed.
        """
        with hydrated_context(self.context):
            async with AsyncClientContext.get_or_create() as client_ctx:
                self._client = client_ctx.client
                self._is_started = True

                if not self.flow_run:
                    self.flow_run = await self.create_flow_run(self.client)
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

                    await self.client.update_flow_run(
                        flow_run_id=self.flow_run.id,
                        flow_version=self.flow.version,
                        empirical_policy=self.flow_run.empirical_policy,
                    )

                await self._telemetry.async_start_span(
                    run=self.flow_run,
                    client=self.client,
                    parameters=self.parameters,
                )

                try:
                    yield self

                except TerminationSignal as exc:
                    self.cancel_all_tasks()
                    await self.handle_crash(exc)
                    raise
                except Exception:
                    # regular exceptions are caught and re-raised to the user
                    raise
                except (Abort, Pause) as exc:
                    if getattr(exc, "state", None):
                        # we set attribute explicitly because
                        # internals will have already called the state change API
                        self.flow_run.state = exc.state
                    raise
                except GeneratorExit:
                    # Do not capture generator exits as crashes
                    raise
                except BaseException as exc:
                    # BaseExceptions are caught and handled as crashes
                    await self.handle_crash(exc)
                    raise
                finally:
                    # If debugging, use the more complete `repr` than the usual `str` description
                    display_state = (
                        repr(self.state) if PREFECT_DEBUG_MODE else str(self.state)
                    )
                    self.logger.log(
                        level=logging.INFO
                        if self.state.is_completed()
                        else logging.ERROR,
                        msg=f"Finished in state {display_state}",
                    )

                    self._is_started = False
                    self._client = None

    # --------------------------
    #
    # The following methods compose the main task run loop
    #
    # --------------------------

    @asynccontextmanager
    async def start(self) -> AsyncGenerator[None, None]:
        async with self.initialize_run():
            with (
                trace.use_span(self._telemetry.span)
                if self._telemetry.span
                else nullcontext()
            ):
                await self.begin_run()

                yield

    @asynccontextmanager
    async def run_context(self):
        timeout_context = timeout_async if self.flow.isasync else timeout
        # reenter the run context to ensure it is up to date for every run
        async with self.setup_run_context():
            try:
                with timeout_context(
                    seconds=self.flow.timeout_seconds,
                    timeout_exc_type=FlowRunTimeoutError,
                ):
                    self.logger.debug(
                        f"Executing flow {self.flow.name!r} for flow run {self.flow_run.name!r}..."
                    )
                    yield self
            except TimeoutError as exc:
                await self.handle_timeout(exc)
            except Exception as exc:
                self.logger.exception("Encountered exception during execution: %r", exc)
                await self.handle_exception(exc)

    async def call_flow_fn(self) -> Coroutine[Any, Any, R]:
        """
        Convenience method to call the flow function. Returns a coroutine if the
        flow is async.
        """
        assert self.flow.isasync, "Flow must be async to be run with AsyncFlowRunEngine"

        result = await call_with_parameters(self.flow.fn, self.parameters)
        await self.handle_success(result)
        return result


def run_flow_sync(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
    return_type: Literal["state", "result"] = "result",
    context: Optional[dict[str, Any]] = None,
) -> Union[R, State, None]:
    engine = FlowRunEngine[P, R](
        flow=flow,
        parameters=parameters,
        flow_run=flow_run,
        wait_for=wait_for,
        context=context,
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
    wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
    return_type: Literal["state", "result"] = "result",
    context: Optional[dict[str, Any]] = None,
) -> Union[R, State, None]:
    engine = AsyncFlowRunEngine[P, R](
        flow=flow,
        parameters=parameters,
        flow_run=flow_run,
        wait_for=wait_for,
        context=context,
    )

    async with engine.start():
        while engine.is_running():
            async with engine.run_context():
                await engine.call_flow_fn()

    return engine.state if return_type == "state" else await engine.result()


def run_generator_flow_sync(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
    return_type: Literal["state", "result"] = "result",
    context: Optional[dict[str, Any]] = None,
) -> Generator[R, None, None]:
    if return_type != "result":
        raise ValueError("The return_type for a generator flow must be 'result'")

    engine = FlowRunEngine[P, R](
        flow=flow,
        parameters=parameters,
        flow_run=flow_run,
        wait_for=wait_for,
        context=context,
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
                        link_state_to_flow_run_result(engine.state, gen_result)
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
    wait_for: Optional[Iterable[PrefectFuture[R]]] = None,
    return_type: Literal["state", "result"] = "result",
    context: Optional[dict[str, Any]] = None,
) -> AsyncGenerator[R, None]:
    if return_type != "result":
        raise ValueError("The return_type for a generator flow must be 'result'")

    engine = AsyncFlowRunEngine[P, R](
        flow=flow,
        parameters=parameters,
        flow_run=flow_run,
        wait_for=wait_for,
        context=context,
    )

    async with engine.start():
        while engine.is_running():
            async with engine.run_context():
                call_args, call_kwargs = parameters_to_args_kwargs(
                    flow.fn, engine.parameters or {}
                )
                gen = flow.fn(*call_args, **call_kwargs)
                try:
                    while True:
                        # can't use anext in Python < 3.10
                        gen_result = await gen.__anext__()
                        # link the current state to the result for dependency tracking
                        link_state_to_flow_run_result(engine.state, gen_result)
                        yield gen_result
                except (StopAsyncIteration, GeneratorExit) as exc:
                    await engine.handle_success(None)
                    if isinstance(exc, GeneratorExit):
                        gen.throw(exc)

    # async generators can't return, but we can raise failures here
    if engine.state.is_failed():
        await engine.result()


def run_flow(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[R]]] = None,
    return_type: Literal["state", "result"] = "result",
    error_logger: Optional[logging.Logger] = None,
    context: Optional[dict[str, Any]] = None,
) -> (
    R
    | State
    | None
    | Coroutine[Any, Any, R | State | None]
    | Generator[R, None, None]
    | AsyncGenerator[R, None]
):
    ret_val: Union[
        R,
        State,
        None,
        Coroutine[Any, Any, R | State | None],
        Generator[R, None, None],
        AsyncGenerator[R, None],
    ] = None

    try:
        kwargs: dict[str, Any] = dict(
            flow=flow,
            flow_run=flow_run,
            parameters=_flow_parameters(
                flow=flow, flow_run=flow_run, parameters=parameters
            ),
            wait_for=wait_for,
            return_type=return_type,
            context=context,
        )

        if flow.isasync and flow.isgenerator:
            ret_val = run_generator_flow_async(**kwargs)
        elif flow.isgenerator:
            ret_val = run_generator_flow_sync(**kwargs)
        elif flow.isasync:
            ret_val = run_flow_async(**kwargs)
        else:
            ret_val = run_flow_sync(**kwargs)
    except (Abort, Pause):
        raise
    except:
        if error_logger:
            error_logger.error(
                "Engine execution exited with unexpected exception", exc_info=True
            )
        raise
    return ret_val


def _flow_parameters(
    flow: Flow[P, R], flow_run: Optional[FlowRun], parameters: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    if parameters:
        # This path is taken when a flow is being called directly with
        # parameters, in that case just return the parameters as-is.
        return parameters

    # Otherwise the flow is being executed indirectly and we may need to grab
    # the parameters from the flow run. We also need to resolve any default
    # parameters that are defined on the flow function itself.

    parameters = flow_run.parameters if flow_run else {}
    call_args, call_kwargs = parameters_to_args_kwargs(flow.fn, parameters)
    return get_call_parameters(flow.fn, call_args, call_kwargs)


def run_flow_in_subprocess(
    flow: "Flow[..., Any]",
    flow_run: "FlowRun | None" = None,
    parameters: dict[str, Any] | None = None,
    wait_for: Iterable[PrefectFuture[Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> multiprocessing.context.SpawnProcess:
    """
    Run a flow in a subprocess.

    Note the result of the flow will only be accessible if the flow is configured to
    persist its result.

    Args:
        flow: The flow to run.
        flow_run: The flow run object containing run metadata.
        parameters: The parameters to use when invoking the flow.
        wait_for: The futures to wait for before starting the flow.
        context: A serialized context to hydrate before running the flow. If not provided,
            the current context will be used. A serialized context should be provided if
            this function is called in a separate memory space from the parent run (e.g.
            in a subprocess or on another machine).

    Returns:
        A multiprocessing.context.SpawnProcess representing the process that is running the flow.
    """
    from prefect.flow_engine import run_flow

    @wraps(run_flow)
    def run_flow_with_env(
        *args: Any,
        env: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        """
        Wrapper function to update environment variables and settings before running the flow.
        """
        os.environ.update(env or {})
        settings_context = get_settings_context()
        # Create a new settings context with a new settings object to pick up the updated
        # environment variables
        with SettingsContext(
            profile=settings_context.profile,
            settings=Settings(),
        ):
            with handle_engine_signals(getattr(flow_run, "id", None)):
                maybe_coro = run_flow(*args, **kwargs)
                if asyncio.iscoroutine(maybe_coro):
                    # This is running in a brand new process, so there won't be an existing
                    # event loop.
                    asyncio.run(maybe_coro)

    ctx = multiprocessing.get_context("spawn")

    context = context or serialize_context()

    process = ctx.Process(
        target=cloudpickle_wrapped_call(
            run_flow_with_env,
            env=get_current_settings().to_environment_variables(exclude_unset=True)
            | os.environ
            | {
                # TODO: make this a thing we can pass into the engine
                "PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS": "false",
            },
            flow=flow,
            flow_run=flow_run,
            parameters=parameters,
            wait_for=wait_for,
            context=context,
        ),
    )
    process.start()

    return process
