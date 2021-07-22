import contextvars
from functools import wraps
from types import TracebackType
from typing import Any, Dict, Iterable, Type, TYPE_CHECKING

import httpx

from prefect.core.utilities import sync
from prefect.orion import schemas
from prefect.orion.api.server import app as orion_app

if TYPE_CHECKING:
    from prefect.core import Flow


class OrionClient:
    def __init__(self, http_client: httpx.AsyncClient = None) -> None:
        # If not given an httpx client, create one that connects to an ephemeral app
        self._client = http_client or httpx.AsyncClient(
            app=orion_app, base_url="http://ephemeral"
        )
        self._context_token: contextvars.Token = None

    async def post(self, route: str, **kwargs) -> httpx.Response:
        response = await self._client.post(route, **kwargs)
        # TODO: We may not _always_ want to raise bad status codes but for now we will
        #       because response.json() will throw misleading errors and this will ease
        #       development
        response.raise_for_status()
        return response

    async def get(self, route: str) -> httpx.Response:
        response = await self._client.get(route)
        response.raise_for_status()
        return response

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] = None,
        exc_value: BaseException = None,
        traceback: TracebackType = None,
    ):
        await self._client.__aexit__(exc_type, exc_value, traceback)

    # API methods ----------------------------------------------------------------------

    async def hello(self) -> httpx.Response:
        return await self.post("/hello")

    async def create_flow(self, flow: "Flow") -> str:
        flow_data = schemas.actions.FlowCreate(
            name=flow.name,
            tags=flow.tags,
            parameters=flow.parameters,
        )
        response = await self.post("/flows/", json=flow_data.json_dict())

        flow_id = response.json().get("id")
        if not flow_id:
            raise Exception(f"Malformed response: {response}")

        # Return the id of the created flow
        return flow_id

    async def read_flow(self, flow_id: str) -> schemas.api.Flow:
        response = await self.get(f"/flows/{flow_id}")
        return schemas.api.Flow(**response.json())

    async def create_flow_run(
        self,
        flow: "Flow",
        parameters: Dict[str, Any] = None,
        context: dict = None,
        extra_tags: Iterable[str] = None,
        parent_task_run_id: str = None,
    ) -> str:
        tags = set(flow.tags).union(extra_tags or [])
        parameters = parameters or {}
        context = context or {}

        # Retrieve the flow id
        flow_id = await self.create_flow(flow)

        flow_run_data = schemas.actions.FlowRunCreate(
            flow_id=flow_id,
            flow_version=flow.version,
            parameters=parameters,
            context=context,
            tags=list(tags),
            parent_task_run_id=parent_task_run_id,
        )

        response = await self.post("/flow_runs/", json=flow_run_data.json_dict())
        flow_run_id = response.json().get("id")
        if not flow_run_id:
            raise Exception(f"Malformed response: {response}")

        return flow_run_id

    async def read_flow_run(self, flow_run_id: str) -> schemas.api.FlowRun:
        response = await self.get(f"/flow_runs/{flow_run_id}")
        return schemas.api.FlowRun(**response.json())


# A synchronous API could look like this...


def _create_sync_api(method):
    """
    Create a synchronous version of a function with a transient async client context
    """

    @wraps(method)
    async def run_with_client(*args, **kwargs):
        async with OrionClient() as client:
            return await method(client, *args, **kwargs)

    return sync(run_with_client)


read_flow = _create_sync_api(OrionClient.read_flow)
read_flow_run = _create_sync_api(OrionClient.read_flow_run)
