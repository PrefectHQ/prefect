import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import (
    Any,
    Coroutine,
    Dict,
    Generic,
    Iterable,
    Optional,
    TypeVar,
    cast,
)

import anyio
from typing_extensions import ParamSpec

from prefect import Flow, Task, get_client
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import FlowRun, TaskRun
from prefect.context import FlowRunContext
from prefect.futures import PrefectFuture
from prefect.results import ResultFactory
from prefect.server.schemas.states import State
from prefect.states import Completed, Failed, Running
from prefect.utilities.asyncutils import A, Async
from prefect.utilities.engine import (
    _resolve_custom_flow_run_name,
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
        state = Running()
        return await self.set_state(state)

    async def set_subflow_state(self, state: State) -> State:
        pass

    async def set_state(self, state: State) -> State:
        """ """
        state = await propose_state(self.client, state, flow_run_id=self.flow_run.id)  # type: ignore
        self.flow_run.state = state  # type: ignore
        self.flow_run.state_name = state.name  # type: ignore
        self.flow_run.state_type = state.type  # type: ignore
        await self.set_subflow_state(state)
        return state

    async def handle_success(self, result: R) -> R:
        await self.set_state(Completed())
        return result

    async def handle_exception(self, exc: Exception):
        await self.handle_failure(exc)

    async def handle_failure(self, exc: Exception) -> None:
        await self.set_state(Failed())
        raise exc

    async def create_subflow_task_run(self, client: PrefectClient) -> TaskRun:
        pass

    async def create_flow_run(self, client: PrefectClient) -> FlowRun:
        flow_run_ctx = FlowRunContext.get()

        # this is a subflow run
        parent_task_run = None
        if flow_run_ctx:
            parent_task_run = await self.create_subflow_task_run()

        try:
            flow_run_name = _resolve_custom_flow_run_name(
                flow=self.flow, parameters=self.parameters
            )
        except TypeError:
            flow_run_name = None

        flow_run = await client.create_flow_run(
            flow=self.flow,
            name=flow_run_name,
            parameters=self.parameters,
            state=Running(),
        )
        return flow_run

    @asynccontextmanager
    async def start(self):
        """
        - sets state to running
        - initialize flow run logger
        """
        async with get_client() as client:
            self._client = client
            self._is_started = True

            if not self.flow_run:
                self.flow_run = await self.create_flow_run(client)

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
                yield self

        self._is_started = False
        self._client = None

    async def get_client(self):
        if not self._is_started:
            raise RuntimeError("Engine has not started.")
        else:
            return self._client

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
) -> R | None:
    """
    Runs a flow against the API.

    We will most likely want to use this logic as a wrapper and return a coroutine for type inference.
    """

    engine = FlowRunEngine[P, R](flow, parameters, flow_run)
    async with engine.start() as state:
        # This is a context manager that keeps track of the state of the flow run.
        await state.begin_run()

        while state.is_pending():
            await asyncio.sleep(1)
            await state.begin_run()

        while state.is_running():
            try:
                # This is where the flow is actually run.
                result = cast(R, await flow.fn(**(parameters or {})))  # type: ignore
                # If the flow run is successful, finalize it.
                await state.handle_success(result)
                return result

            except Exception as exc:
                # If the flow fails, and we have retries left, set the flow to retrying.
                await state.handle_exception(exc)

        return await state.result()
