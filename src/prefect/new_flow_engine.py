import inspect
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import (
    Any,
    Coroutine,
    Dict,
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

import anyio
import anyio._backends._asyncio
from sniffio import AsyncLibraryNotFoundError
from typing_extensions import ParamSpec

from prefect import Task, get_client
from prefect.client.orchestration import SyncPrefectClient
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.sorting import FlowRunSort
from prefect.context import FlowRunContext
from prefect.deployments import load_flow_from_flow_run
from prefect.exceptions import Abort, Pause
from prefect.flows import Flow, load_flow_from_entrypoint
from prefect.futures import PrefectFuture, resolve_futures_to_states
from prefect.logging.loggers import flow_run_logger, get_logger
from prefect.results import ResultFactory
from prefect.states import (
    Pending,
    Running,
    State,
    exception_to_crashed_state,
    exception_to_failed_state,
    return_value_to_state,
)
from prefect.utilities.asyncutils import A, Async, run_sync
from prefect.utilities.callables import parameters_to_args_kwargs
from prefect.utilities.engine import (
    _resolve_custom_flow_run_name,
    propose_state_sync,
)

P = ParamSpec("P")
R = TypeVar("R")


def load_flow_and_flow_run(flow_run_id: UUID) -> Tuple[FlowRun, Flow]:
    ## TODO: add error handling to update state and log tracebacks
    entrypoint = os.environ.get("PREFECT__FLOW_ENTRYPOINT")

    client = get_client(sync_client=True)
    flow_run = client.read_flow_run(flow_run_id)
    flow = (
        load_flow_from_entrypoint(entrypoint)
        if entrypoint
        else run_sync(load_flow_from_flow_run(flow_run, client=client))
    )

    return flow_run, flow


@dataclass
class FlowRunEngine(Generic[P, R]):
    flow: Optional[Union[Flow[P, R], Flow[P, Coroutine[Any, Any, R]]]] = None
    parameters: Optional[Dict[str, Any]] = None
    flow_run: Optional[FlowRun] = None
    flow_run_id: Optional[UUID] = None
    logger: logging.Logger = field(default_factory=lambda: get_logger("engine"))
    _is_started: bool = False
    _client: Optional[SyncPrefectClient] = None
    short_circuit: bool = False

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

    def begin_run(self) -> State:
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
            _result = run_sync(_result)
        return _result

    def handle_success(self, result: R) -> R:
        result_factory = getattr(FlowRunContext.get(), "result_factory", None)
        if result_factory is None:
            raise ValueError("Result factory is not set")
        terminal_state = run_sync(
            return_value_to_state(
                run_sync(resolve_futures_to_states(result)),
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
        state = run_sync(
            exception_to_failed_state(
                exc,
                message=msg or "Flow run encountered an exception:",
                result_factory=result_factory
                or getattr(context, "result_factory", None),
            )
        )
        state = self.set_state(state)
        if self.state.is_scheduled():
            state = self.set_state(Running())
        return state

    def handle_crash(self, exc: BaseException) -> None:
        state = run_sync(exception_to_crashed_state(exc))
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
            # reuse the logic from the TaskRunEngine to ensure parents are created correctly
            parent_task = Task(
                name=self.flow.name, fn=self.flow.fn, version=self.flow.version
            )
            parent_task_run = run_sync(
                parent_task.create_run(
                    client=self.client,
                    flow_run_context=flow_run_ctx,
                    parameters=self.parameters,
                )
            )

            # check if there is already a flow run for this subflow
            if subflow_run := self.load_subflow_run(
                parent_task_run=parent_task_run, client=client, context=flow_run_ctx
            ):
                return subflow_run

        try:
            flow_run_name = _resolve_custom_flow_run_name(
                flow=self.flow, parameters=parameters
            )
        except TypeError:
            flow_run_name = None

        flow_run = client.create_flow_run(
            flow=self.flow,
            name=flow_run_name,
            parameters=self.flow.serialize_parameters(parameters),
            state=Pending(),
            parent_task_run_id=getattr(parent_task_run, "id", None),
        )
        return flow_run

    @contextmanager
    def enter_run_context(self, client: Optional[SyncPrefectClient] = None):
        if client is None:
            client = self.client
        if not self.flow_run:
            raise ValueError("Flow run not set")

        self.flow_run = client.read_flow_run(self.flow_run.id)

        # if running in a completely synchronous frame, anyio will not detect the
        # backend to use for the task group
        try:
            task_group = anyio.create_task_group()
        except AsyncLibraryNotFoundError:
            task_group = anyio._backends._asyncio.TaskGroup()

        with FlowRunContext(
            flow=self.flow,
            log_prints=self.flow.log_prints or False,
            flow_run=self.flow_run,
            parameters=self.parameters,
            client=client,
            background_tasks=task_group,
            result_factory=run_sync(ResultFactory.from_flow(self.flow)),
            task_runner=self.flow.task_runner.duplicate(),
        ):
            # set the logger to the flow run logger
            current_logger = self.logger
            try:
                self.logger = flow_run_logger(flow_run=self.flow_run, flow=self.flow)
                yield
            finally:
                self.logger = current_logger

    @contextmanager
    def start(self):
        """
        Enters a client context and creates a flow run if needed.
        """

        with get_client(sync_client=True) as client:
            self._client = client
            self._is_started = True

            # this conditional is engaged whenever a run is triggered via deployment
            if self.flow_run_id and not self.flow:
                self.flow_run = client.read_flow_run(self.flow_run_id)
                try:
                    self.flow = self.load_flow(client)
                except Exception as exc:
                    self.handle_exception(
                        exc,
                        msg="Failed to load flow from entrypoint.",
                    )
                    self.short_circuit = True

            if not self.flow_run:
                self.flow_run = self.create_flow_run(client)
                self.logger.debug(f'Created flow run "{self.flow_run.id}"')

            # validate prior to context so that context receives validated params
            if self.flow.should_validate_parameters:
                try:
                    self.parameters = self.flow.validate_parameters(
                        self.parameters or {}
                    )
                except Exception as exc:
                    self.handle_exception(
                        exc,
                        msg="Validation of flow parameters failed with error",
                        result_factory=run_sync(ResultFactory.from_flow(self.flow)),
                    )
                    self.short_circuit = True
            try:
                yield self
            except Exception:
                # regular exceptions are caught and re-raised to the user
                raise
            except (Abort, Pause):
                raise
            except BaseException as exc:
                # BaseExceptions are caught and handled as crashes
                self.handle_crash(exc)
                raise
            finally:
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


async def run_flow_async(
    flow: Optional[Flow[P, Coroutine[Any, Any, R]]] = None,
    flow_run: Optional[FlowRun] = None,
    flow_run_id: Optional[UUID] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, None]:
    """
    Runs a flow against the API.

    We will most likely want to use this logic as a wrapper and return a coroutine for type inference.
    """

    engine = FlowRunEngine[P, R](flow, parameters, flow_run, flow_run_id)

    # This is a context manager that keeps track of the state of the flow run.
    with engine.start() as run:
        run.begin_run()

        while run.is_running():
            with run.enter_run_context():
                try:
                    # This is where the flow is actually run.
                    call_args, call_kwargs = parameters_to_args_kwargs(
                        flow.fn, run.parameters or {}
                    )
                    result = cast(R, await flow.fn(*call_args, **call_kwargs))  # type: ignore
                    # If the flow run is successful, finalize it.
                    run.handle_success(result)

                except Exception as exc:
                    # If the flow fails, and we have retries left, set the flow to retrying.
                    run.handle_exception(exc)

        if return_type == "state":
            return run.state
        return run.result()


def run_flow_sync(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    engine = FlowRunEngine[P, R](flow, parameters, flow_run)

    # This is a context manager that keeps track of the state of the flow run.
    with engine.start() as run:
        run.begin_run()

        while run.is_running():
            with run.enter_run_context():
                try:
                    # This is where the flow is actually run.
                    call_args, call_kwargs = parameters_to_args_kwargs(
                        flow.fn, run.parameters or {}
                    )
                    result = cast(R, flow.fn(*call_args, **call_kwargs))  # type: ignore
                    # If the flow run is successful, finalize it.
                    run.handle_success(result)

                except Exception as exc:
                    # If the flow fails, and we have retries left, set the flow to retrying.
                    run.handle_exception(exc)

        if return_type == "state":
            return run.state
        return run.result()


def run_flow(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    kwargs = dict(
        flow=flow,
        flow_run=flow_run,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
    )
    if flow.isasync:
        return run_flow_async(**kwargs)
    else:
        return run_flow_sync(**kwargs)
