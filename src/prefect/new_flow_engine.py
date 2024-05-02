import asyncio
import inspect
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import (
    Any,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    Literal,
    Optional,
    TypeVar,
    Union,
    cast,
)

import anyio
import anyio._backends._asyncio
from sniffio import AsyncLibraryNotFoundError
from typing_extensions import ParamSpec

from prefect import Flow, Task, get_client
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.sorting import FlowRunSort
from prefect.context import FlowRunContext
from prefect.futures import PrefectFuture, resolve_futures_to_states
from prefect.logging.loggers import flow_run_logger
from prefect.results import ResultFactory
from prefect.states import (
    Pending,
    Running,
    State,
    exception_to_failed_state,
    return_value_to_state,
)
from prefect.utilities.asyncutils import A, Async, run_sync
from prefect.utilities.callables import parameters_to_args_kwargs
from prefect.utilities.engine import (
    _dynamic_key_for_task_run,
    _resolve_custom_flow_run_name,
    collect_task_run_inputs,
    propose_state,
)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class FlowRunEngine(Generic[P, R]):
    flow: Union[Flow[P, R], Flow[P, Coroutine[Any, Any, R]]]
    parameters: Optional[Dict[str, Any]] = None
    flow_run: Optional[FlowRun] = None
    _is_started: bool = False
    _client: Optional[PrefectClient] = None
    short_circuit: bool = False

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
        return self.flow_run.state  # type: ignore

    async def begin_run(self) -> State:
        new_state = Running()
        state = await self.set_state(new_state)
        while state.is_pending():
            await asyncio.sleep(1)
            state = await self.set_state(new_state)
        return state

    async def set_state(self, state: State) -> State:
        """ """
        # prevents any state-setting activity
        if self.short_circuit:
            return self.state

        state = await propose_state(self.client, state, flow_run_id=self.flow_run.id)  # type: ignore
        self.flow_run.state = state  # type: ignore
        self.flow_run.state_name = state.name  # type: ignore
        self.flow_run.state_type = state.type  # type: ignore
        return state

    async def result(self, raise_on_failure: bool = True) -> "Union[R, State, None]":
        _result = self.state.result(raise_on_failure=raise_on_failure, fetch=True)  # type: ignore
        # state.result is a `sync_compatible` function that may or may not return an awaitable
        # depending on whether the parent frame is sync or not
        if inspect.isawaitable(_result):
            _result = await _result
        return _result

    async def handle_success(self, result: R) -> R:
        result_factory = getattr(FlowRunContext.get(), "result_factory", None)
        if result_factory is None:
            raise ValueError("Result factory is not set")
        terminal_state = await return_value_to_state(
            await resolve_futures_to_states(result),
            result_factory=result_factory,
        )
        await self.set_state(terminal_state)
        return result

    async def handle_exception(
        self,
        exc: Exception,
        msg: Optional[str] = None,
        result_factory: Optional[ResultFactory] = None,
    ) -> State:
        context = FlowRunContext.get()
        state = await exception_to_failed_state(
            exc,
            message=msg or "Flow run encountered an exception:",
            result_factory=result_factory or getattr(context, "result_factory", None),
        )
        state = await self.set_state(state)
        if self.state.is_scheduled():
            state = await self.set_state(Running())
        return state

    async def load_subflow_run(
        self, parent_task_run: TaskRun, client: PrefectClient, context: FlowRunContext
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
                return flow_runs[-1]

    async def create_subflow_task_run(
        self, client: PrefectClient, context: FlowRunContext
    ) -> TaskRun:
        """
        Adds a task to a parent flow run that represents the execution of a subflow run.

        The task run is referred to as the "parent task run" of the subflow and will be kept
        in sync with the subflow run's state by the orchestration engine.
        """
        dummy_task = Task(
            name=self.flow.name, fn=self.flow.fn, version=self.flow.version
        )
        task_inputs = {
            k: await collect_task_run_inputs(v)
            for k, v in (self.parameters or {}).items()
        }
        parent_task_run = await client.create_task_run(
            task=dummy_task,
            flow_run_id=(
                context.flow_run.id
                if getattr(context, "flow_run", None)
                and isinstance(context.flow_run, FlowRun)
                else None
            ),
            dynamic_key=_dynamic_key_for_task_run(context, dummy_task),  # type: ignore
            task_inputs=task_inputs,  # type: ignore
            state=Pending(),
        )
        return parent_task_run

    async def create_flow_run(self, client: PrefectClient) -> FlowRun:
        flow_run_ctx = FlowRunContext.get()
        parameters = self.parameters or {}

        parent_task_run = None

        # this is a subflow run
        if flow_run_ctx:
            # get the parent task run
            parent_task_run = await self.create_subflow_task_run(
                client=client, context=flow_run_ctx
            )

            # check if there is already a flow run for this subflow
            if subflow_run := await self.load_subflow_run(
                parent_task_run=parent_task_run, client=client, context=flow_run_ctx
            ):
                return subflow_run

        try:
            flow_run_name = _resolve_custom_flow_run_name(
                flow=self.flow, parameters=parameters
            )
        except TypeError:
            flow_run_name = None

        flow_run = await client.create_flow_run(
            flow=self.flow,
            name=flow_run_name,
            parameters=self.flow.serialize_parameters(parameters),
            state=Pending(),
            parent_task_run_id=getattr(parent_task_run, "id", None),
        )
        return flow_run

    @asynccontextmanager
    async def enter_run_context(self, client: Optional[PrefectClient] = None):
        if client is None:
            client = self.client
        if not self.flow_run:
            raise ValueError("Flow run not set")

        self.flow_run = await client.read_flow_run(self.flow_run.id)
        task_runner = self.flow.task_runner.duplicate()

        async with AsyncExitStack() as stack:
            task_runner = await stack.enter_async_context(
                self.flow.task_runner.duplicate().start()
            )
            stack.enter_context(
                FlowRunContext(
                    flow=self.flow,
                    log_prints=self.flow.log_prints or False,
                    flow_run=self.flow_run,
                    parameters=self.parameters,
                    client=client,
                    background_tasks=anyio.create_task_group(),
                    result_factory=await ResultFactory.from_flow(self.flow),
                    task_runner=task_runner,
                )
            )
            self.logger = flow_run_logger(flow_run=self.flow_run, flow=self.flow)
            yield

    @contextmanager
    def enter_run_context_sync(self, client: Optional[PrefectClient] = None):
        if client is None:
            client = self.client
        if not self.flow_run:
            raise ValueError("Flow run not set")

        self.flow_run = run_sync(client.read_flow_run(self.flow_run.id))

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
            task_runner=self.flow.task_runner,
        ):
            self.logger = flow_run_logger(flow_run=self.flow_run, flow=self.flow)
            yield

    @asynccontextmanager
    async def start(self):
        """
        Enters a client context and creates a flow run if needed.
        """
        async with get_client() as client:
            self._client = client
            self._is_started = True

            if not self.flow_run:
                self.flow_run = await self.create_flow_run(client)

            # validate prior to context so that context receives validated params
            if self.flow.should_validate_parameters:
                try:
                    self.parameters = self.flow.validate_parameters(
                        self.parameters or {}
                    )
                except Exception as exc:
                    await self.handle_exception(
                        exc,
                        msg="Validation of flow parameters failed with error",
                        result_factory=await ResultFactory.from_flow(self.flow),
                    )
                    self.short_circuit = True
            try:
                yield self
            finally:
                self._is_started = False
                self._client = None

    @contextmanager
    def start_sync(self):
        """
        Enters a client context and creates a flow run if needed.
        """

        client = get_client()
        run_sync(client.__aenter__())
        self._client = client
        self._is_started = True

        if not self.flow_run:
            self.flow_run = run_sync(self.create_flow_run(client))

        # validate prior to context so that context receives validated params
        if self.flow.should_validate_parameters:
            try:
                self.parameters = self.flow.validate_parameters(self.parameters or {})
            except Exception as exc:
                run_sync(
                    self.handle_exception(
                        exc,
                        msg="Validation of flow parameters failed with error",
                        result_factory=run_sync(ResultFactory.from_flow(self.flow)),
                    )
                )
                self.short_circuit = True
        try:
            yield self
        finally:
            # quickly close client
            run_sync(client.__aexit__(None, None, None))
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


async def run_flow(
    flow: Flow[P, Coroutine[Any, Any, R]],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, None]:
    """
    Runs a flow against the API.

    We will most likely want to use this logic as a wrapper and return a coroutine for type inference.
    """

    engine = FlowRunEngine[P, R](flow, parameters, flow_run)

    # This is a context manager that keeps track of the state of the flow run.
    async with engine.start() as run:
        await run.begin_run()

        while run.is_running():
            async with run.enter_run_context():
                try:
                    # This is where the flow is actually run.
                    call_args, call_kwargs = parameters_to_args_kwargs(
                        flow.fn, run.parameters or {}
                    )
                    result = cast(R, await flow.fn(*call_args, **call_kwargs))  # type: ignore
                    # If the flow run is successful, finalize it.
                    await run.handle_success(result)

                except Exception as exc:
                    # If the flow fails, and we have retries left, set the flow to retrying.
                    await run.handle_exception(exc)

        if return_type == "state":
            return run.state
        return await run.result()


def run_flow_sync(
    flow: Flow[P, R],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> Union[R, State, None]:
    engine = FlowRunEngine[P, R](flow, parameters, flow_run)

    # This is a context manager that keeps track of the state of the flow run.
    with engine.start_sync() as run:
        run_sync(run.begin_run())

        while run.is_running():
            with run.enter_run_context_sync():
                try:
                    # This is where the flow is actually run.
                    call_args, call_kwargs = parameters_to_args_kwargs(
                        flow.fn, run.parameters or {}
                    )
                    result = cast(R, flow.fn(*call_args, **call_kwargs))  # type: ignore
                    # If the flow run is successful, finalize it.
                    run_sync(run.handle_success(result))

                except Exception as exc:
                    # If the flow fails, and we have retries left, set the flow to retrying.
                    run_sync(run.handle_exception(exc))

        if return_type == "state":
            return run.state
        return run_sync(run.result())
