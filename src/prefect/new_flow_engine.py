import asyncio
from contextlib import asynccontextmanager
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
from prefect.utilities.asyncutils import A, Async
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
    flow: Flow[P, Coroutine[Any, Any, R]]
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
        return await self.state.result(raise_on_failure=raise_on_failure, fetch=True)

    async def handle_success(self, result: R) -> R:
        result_factory = getattr(FlowRunContext.get(), "result_factory", None)
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

    async def create_subflow_task_run(
        self, client: PrefectClient, context: FlowRunContext
    ) -> TaskRun:
        dummy_task = Task(
            name=self.flow.name, fn=self.flow.fn, version=self.flow.version
        )
        task_inputs = {
            k: await collect_task_run_inputs(v) for k, v in self.parameters.items()
        }
        parent_task_run = await client.create_task_run(
            task=dummy_task,
            flow_run_id=(
                context.flow_run.id if getattr(context, "flow_run", None) else None
            ),
            dynamic_key=_dynamic_key_for_task_run(context, dummy_task),
            task_inputs=task_inputs,
            state=Pending(),
        )
        return parent_task_run

    async def get_most_recent_flow_run_for_parent_task_run(
        self, client: PrefectClient, parent_task_run: TaskRun
    ) -> "Union[FlowRun, None]":
        """
        Get the most recent flow run associated with the provided parent task run.

        Args:
            - An orchestration client
            - The parent task run to get the most recent flow run for

        Returns:
            The most recent flow run associated with the parent task run or `None` if
            no flow runs are found
        """
        flow_runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                parent_task_run_id={"any_": [parent_task_run.id]}
            ),
            sort=FlowRunSort.EXPECTED_START_TIME_ASC,
        )
        return flow_runs[-1] if flow_runs else None

    async def create_flow_run(self, client: PrefectClient) -> FlowRun:
        flow_run_ctx = FlowRunContext.get()

        parent_task_run = None
        # this is a subflow run
        if flow_run_ctx:
            parent_task_run = await self.create_subflow_task_run(
                client=client, context=flow_run_ctx
            )
            # If the parent task run already completed, return the last flow run
            # associated with the parent task run. This prevents rerunning a completed
            # flow run when the parent task run is rerun.
            most_recent_flow_run = (
                await self.get_most_recent_flow_run_for_parent_task_run(
                    client=client, parent_task_run=parent_task_run
                )
            )
            if most_recent_flow_run:
                return most_recent_flow_run

        try:
            flow_run_name = _resolve_custom_flow_run_name(
                flow=self.flow, parameters=self.parameters
            )
        except TypeError:
            flow_run_name = None

        flow_run = await client.create_flow_run(
            flow=self.flow,
            name=flow_run_name,
            parameters=self.flow.serialize_parameters(self.parameters),
            state=Pending(),
            parent_task_run_id=getattr(parent_task_run, "id", None),
        )
        return flow_run

    @asynccontextmanager
    async def enter_run_context(self, client: Optional[PrefectClient] = None):
        if client is None:
            client = self.client

        self.flow_run = await client.read_flow_run(self.flow_run.id)

        with FlowRunContext(
            flow=self.flow,
            log_prints=self.flow.log_prints or False,
            flow_run=self.flow_run,
            parameters=self.parameters,
            client=client,
            background_tasks=anyio.create_task_group(),
            result_factory=await ResultFactory.from_flow(self.flow),
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
                    self.parameters = self.flow.validate_parameters(self.parameters)
                except Exception as exc:
                    await self.handle_exception(
                        exc,
                        msg="Validation of flow parameters failed with error",
                        result_factory=await ResultFactory.from_flow(self.flow),
                    )
                    self.short_circuit = True

            yield self

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
    flow: Task[P, Coroutine[Any, Any, R]],
    flow_run: Optional[FlowRun] = None,
    parameters: Optional[Dict[str, Any]] = None,
    wait_for: Optional[Iterable[PrefectFuture[A, Async]]] = None,
    return_type: Literal["state", "result"] = "result",
) -> "Union[R, None]":
    """
    Runs a flow against the API.

    We will most likely want to use this logic as a wrapper and return a coroutine for type inference.
    """

    engine = FlowRunEngine[P, R](flow, parameters, flow_run)
    async with engine.start() as run:
        # This is a context manager that keeps track of the state of the flow run.
        await run.begin_run()

        while run.is_running():
            async with run.enter_run_context():
                try:
                    # This is where the flow is actually run.
                    if flow.isasync:
                        result = cast(R, await flow.fn(**(run.parameters or {})))  # type: ignore
                    else:
                        result = cast(R, flow.fn(**(run.parameters or {})))  # type: ignore
                    # If the flow run is successful, finalize it.
                    await run.handle_success(result)

                except Exception as exc:
                    # If the flow fails, and we have retries left, set the flow to retrying.
                    await run.handle_exception(exc)

        if return_type == "state":
            return run.state
        return await run.result()
