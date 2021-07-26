import asyncio
import threading
from types import TracebackType
from typing import TYPE_CHECKING, Any, Dict, Iterable, Tuple, Type, List
from uuid import UUID

import httpx

from prefect.orion import schemas
from prefect.orion.api.server import app as orion_app

if TYPE_CHECKING:
    from prefect.flows import Flow


class OrionClient:
    def __init__(self, http_client: httpx.AsyncClient = None) -> None:
        # If not given an httpx client, create one that connects to an ephemeral app
        self._client = http_client or httpx.AsyncClient(
            app=orion_app, base_url="http://ephemeral"
        )

        # A wrapper is used to call the async httpx interface from a sync context
        self._async_runner = _AsyncRunner()

    def post(self, route: str, **kwargs) -> httpx.Response:
        response = self._async_runner.run(self._client.post(route, **kwargs))
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    def get(self, route: str, **kwargs) -> httpx.Response:
        response = self._async_runner.run(self._client.get(route, **kwargs))
        response.raise_for_status()
        return response

    def __enter__(self):
        self._async_runner.run(self._client.__aenter__())
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] = None,
        exc_value: BaseException = None,
        traceback: TracebackType = None,
    ):

        self._async_runner.run(self._client.__aexit__(None, None, None))
        self._async_runner.stop()

    # API methods ----------------------------------------------------------------------

    def hello(self) -> httpx.Response:
        return self.post("/hello")

    def create_flow(self, flow: "Flow") -> UUID:
        flow_data = schemas.actions.FlowCreate(
            name=flow.name,
            tags=flow.tags,
            parameters=flow.parameters,
        )
        response = self.post("/flows/", json=flow_data.json_dict())

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
        parent_task_run_id: str = None,
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
        )

        response = self.post("/flow_runs/", json=flow_run_data.json_dict())
        flow_run_id = response.json().get("id")
        if not flow_run_id:
            raise Exception(f"Malformed response: {response}")

        return UUID(flow_run_id)

    def read_flow_run(self, flow_run_id: UUID) -> schemas.core.FlowRun:
        response = self.get(f"/flow_runs/{flow_run_id}")
        return schemas.core.FlowRun.parse_obj(response.json())

    def set_flow_run_state(
        self,
        flow_run_id: UUID,
        state: schemas.core.StateType,
        message: str = None,
        data: bytes = None,
    ) -> schemas.responses.SetStateResponse:
        state_data = schemas.actions.StateCreate(
            type=state,
            message=message,
            data=data,
            state_details=schemas.core.StateDetails(
                flow_run_id=flow_run_id,
            ),
        )

        response = self.post(
            f"/flow_runs/{flow_run_id}/set_state",
            json=state_data.json_dict(),
        )
        return schemas.responses.SetStateResponse.parse_obj(response.json())

    def read_flow_run_state(self, flow_run_state_id: UUID) -> schemas.core.State:
        response = self.get(
            f"/flow_run_states/{flow_run_state_id}",
        )
        return schemas.core.State.parse_obj(response.json())

    def read_flow_run_states(self, flow_run_id: UUID) -> List[schemas.core.State]:
        response = self.get("/flow_run_states/", params=dict(flow_run_id=flow_run_id))
        return [schemas.core.State.parse_obj(obj) for obj in response.json()]


class _AsyncRunner:
    def __init__(self) -> None:
        self.thread, self.event_loop = self._create_threaded_event_loop()

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

    def run(self, coro):
        if not self.event_loop:
            raise ValueError("Event loop has not been created.")
        if not self.event_loop.is_running():
            raise ValueError("Event loop is not running.")

        future = asyncio.run_coroutine_threadsafe(coro, loop=self.event_loop)
        result = future.result()

        return result

    def stop(self):
        if self.event_loop.is_running():
            self.event_loop.stop()
