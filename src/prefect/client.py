import asyncio
import threading
import base64
import pickle
from typing import TYPE_CHECKING, Any, Dict, Iterable, Tuple, List, Set
from uuid import UUID
from contextlib import contextmanager
from multiprocessing import current_process

import pydantic
import httpx
import cloudpickle

import prefect
from prefect.orion import schemas
from prefect.orion.schemas.data import (
    OrionDataDocument,
    create_datadoc,
    Base64String,
    get_datadoc_subclass,
    DataDocument,
)
from prefect.orion.api.server import app as orion_app

if TYPE_CHECKING:
    from prefect.flows import Flow
    from prefect.tasks import Task


class OrionClient:
    def __init__(
        self, host: str = prefect.settings.orion_host, httpx_settings: dict = None
    ) -> None:
        httpx_settings = httpx_settings or {}

        if host:
            self._client = httpx.Client(base_url=host, **httpx_settings)
        else:
            # Create an ephemeral app client
            self._client = _ASGIClient(app=orion_app, httpx_settings=httpx_settings)

    def post(self, route: str, **kwargs) -> httpx.Response:
        response = self._client.post(route, **kwargs)
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    def get(self, route: str, **kwargs) -> httpx.Response:
        response = self._client.get(route, **kwargs)
        response.raise_for_status()
        return response

    # API methods ----------------------------------------------------------------------

    def hello(self) -> httpx.Response:
        return self.post("/hello")

    def create_flow(self, flow: "Flow") -> UUID:
        flow_data = schemas.actions.FlowCreate(
            name=flow.name,
            tags=flow.tags,
            parameters=flow.parameters,
        )
        response = self.post("/flows/", json=flow_data.dict(json_compatible=True))

        flow_id = response.json().get("id")
        if not flow_id:
            raise Exception(f"Malformed response: {response}")

        # Return the id of the created flow
        return UUID(flow_id)

    def read_flow(self, flow_id: UUID) -> schemas.core.Flow:
        response = self.get(f"/flows/{flow_id}")
        return schemas.core.Flow.parse_obj(response.json())

    def create_flow_run(
        self,
        flow: "Flow",
        parameters: Dict[str, Any] = None,
        context: dict = None,
        extra_tags: Iterable[str] = None,
        parent_task_run_id: UUID = None,
        state: schemas.states.State = None,
    ) -> UUID:
        tags = set(flow.tags).union(extra_tags or [])
        parameters = parameters or {}
        context = context or {}

        # Retrieve the flow id
        flow_id = self.create_flow(flow)

        flow_run_data = schemas.actions.FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            parameters=parameters,
            context=context,
            tags=list(tags),
            parent_task_run_id=parent_task_run_id,
            state=state,
        )

        response = self.post(
            "/flow_runs/", json=flow_run_data.dict(json_compatible=True)
        )
        flow_run_id = response.json().get("id")
        if not flow_run_id:
            raise Exception(f"Malformed response: {response}")

        return UUID(flow_run_id)

    def read_flow_run(self, flow_run_id: UUID) -> schemas.core.FlowRun:
        response = self.get(f"/flow_runs/{flow_run_id}")
        return schemas.core.FlowRun.parse_obj(response.json())

    def persist_data(
        self,
        data: bytes,
    ) -> OrionDataDocument:
        response = self.post("/data/persist", json=Base64String.from_bytes(data).dict())
        return OrionDataDocument.parse_obj(response.json())

    def retrieve_data(
        self,
        orion_datadoc: OrionDataDocument,
    ) -> bytes:
        response = self.post(
            "/data/retrieve", json=orion_datadoc.dict(json_compatible=True)
        )
        return Base64String.parse_obj(response.json()).to_bytes()

    def persist_object(self, obj: Any, encoder: str = "cloudpickle"):
        datadoc = create_datadoc(encoding=encoder, data=obj)
        return self.persist_data(datadoc.json().encode())

    def retrieve_object(self, orion_datadoc: OrionDataDocument) -> Any:
        datadoc = DataDocument.parse_raw(self.retrieve_data(orion_datadoc))
        return datadoc.to_subtype().read()

    def set_flow_run_state(
        self,
        flow_run_id: UUID,
        state: schemas.states.State,
    ) -> schemas.responses.SetStateResponse:
        state_data = schemas.actions.StateCreate(
            type=state.type,
            message=state.message,
            data=state.data,
            state_details=state.state_details,
        )
        state_data.state_details.flow_run_id = flow_run_id

        # Attempt to serialize the given data
        try:
            state_data_json = state_data.dict(json_compatible=True)
        except TypeError:
            # Drop the user data
            state_data.data = None
            state_data_json = state_data.dict(json_compatible=True)

        response = self.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=state_data_json,
        )
        return schemas.responses.SetStateResponse.parse_obj(response.json())

    def read_flow_run_states(self, flow_run_id: UUID) -> List[schemas.states.State]:
        response = self.get("/flow_run_states/", params=dict(flow_run_id=flow_run_id))
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())

    def create_task_run(
        self,
        task: "Task",
        flow_run_id: UUID,
        extra_tags: Iterable[str] = None,
        state: schemas.states.State = None,
    ) -> UUID:
        tags = set(task.tags).union(extra_tags or [])

        task_run_data = schemas.actions.TaskRunCreate(
            flow_run_id=flow_run_id,
            task_key=task.task_key,
            dynamic_key=task.dynamic_key,
            tags=list(tags),
            empirical_policy=schemas.core.TaskRunPolicy(
                max_retries=task.retries,
                retry_delay_seconds=task.retry_delay_seconds,
            ),
            state=state,
        )

        response = self.post(
            "/task_runs/", json=task_run_data.dict(json_compatible=True)
        )
        task_run_id = response.json().get("id")
        if not task_run_id:
            raise Exception(f"Malformed response: {response}")

        return UUID(task_run_id)

    def read_task_run(self, task_run_id: UUID) -> schemas.core.TaskRun:
        response = self.get(f"/task_runs/{task_run_id}")
        return schemas.core.TaskRun.parse_obj(response.json())

    def set_task_run_state(
        self,
        task_run_id: UUID,
        state: schemas.states.State,
    ) -> schemas.responses.SetStateResponse:
        state_data = schemas.actions.StateCreate(
            type=state.type,
            message=state.message,
            data=state.data,
            state_details=state.state_details,
        )
        state_data.state_details.task_run_id = task_run_id

        # Attempt to serialize the given data
        try:
            state_data_json = state_data.dict(json_compatible=True)
        except TypeError:
            # Drop the user data
            state_data.data = None
            state_data_json = state_data.dict(json_compatible=True)

        response = self.post(
            f"/task_runs/{task_run_id}/set_state",
            json=state_data_json,
        )
        return schemas.responses.SetStateResponse.parse_obj(response.json())

    def read_task_run_states(self, task_run_id: UUID) -> List[schemas.states.State]:
        response = self.get("/task_run_states/", params=dict(task_run_id=task_run_id))
        return pydantic.parse_obj_as(List[schemas.states.State], response.json())


class _ThreadedEventLoop:
    """
    Spawns an event loop in a daemonic thread.

    Creating a new event loop that runs in a child thread prevents us from throwing
    exceptions when there is already an event loop in the main thread and prevents
    synchronous code in the main thread from blocking the event loop from executing.

    These _cannot_ be shared across processes. We use an `EVENT_LOOPS` global to ensure
    that there is a single instance available per process.
    """

    def __init__(self) -> None:
        self._thread, self._loop = self._create_threaded_event_loop()

    def _create_threaded_event_loop(
        self,
    ) -> Tuple[threading.Thread, asyncio.AbstractEventLoop]:
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        loop = asyncio.new_event_loop()

        t = threading.Thread(target=start_loop, args=(loop,), daemon=True)
        t.start()

        return t, loop

    def run_coro(self, coro):
        if not self._loop:
            raise ValueError("Event loop has not been created.")
        if not self._loop.is_running():
            raise ValueError("Event loop is not running.")

        future = asyncio.run_coroutine_threadsafe(coro, loop=self._loop)
        result = future.result()

        return result

    def __del__(self):
        if self._loop and self._loop.is_running():
            self._loop.stop()


# Mapping of PID to a lazily instantiated shared event-loop per process
EVENT_LOOPS: Dict[int, _ThreadedEventLoop] = {}


def _get_process_event_loop():
    """
    Get or create a `_ThreadedEventLoop` for the current process
    """
    pid = current_process().pid
    if pid not in EVENT_LOOPS:
        EVENT_LOOPS[pid] = _ThreadedEventLoop()

    return EVENT_LOOPS[pid]


class _ASGIClient:
    """
    Creates a synchronous wrapper for calling an ASGI application's routes using
    temporary `httpx.AsyncClient` instances.

    Requires a `_ThreadedEventLoop` to submit async work without blocking the main
    thread.
    """

    def __init__(self, app, httpx_settings: dict) -> None:
        self._event_loop = _get_process_event_loop()
        self.app = app
        self.httpx_settings = httpx_settings

    @contextmanager
    def _httpx_client(self):
        """
        Creates a temporary httpx.AsyncClient and cleans up on exit by explicitly
        running `aclose()` since we cannot use `async with` in a synchronous context.

        Since this client is created per request, we are forfeiting the benefits of
        a long-lived HTTP session. However, since this is only intended to be used with
        an ASGI application running in-process, there should not be a meaningful change
        in performance.
        """
        client = httpx.AsyncClient(
            app=self.app, base_url="http://ephemeral", **self.httpx_settings
        )
        try:
            yield client
        finally:
            self._event_loop.run_coro(client.aclose())

    # httpx.Client methods -------------------------------------------------------------

    def get(self, route: str, **kwargs: Any) -> httpx.Response:
        with self._httpx_client() as client:
            return self._event_loop.run_coro(client.get(route, **kwargs))

    def post(self, route: str, **kwargs: Any) -> httpx.Response:
        with self._httpx_client() as client:
            return self._event_loop.run_coro(client.post(route, **kwargs))
