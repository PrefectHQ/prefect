import httpx

import contextvars
from typing import TYPE_CHECKING, Iterable, Dict, Any, Optional

from prefect.orion import api
from prefect.core.utilities import sync

if TYPE_CHECKING:
    from prefect.core.flow import Flow


# Singleton for storing the default client for the current frame
_CLIENT: contextvars.ContextVar["Client"] = contextvars.ContextVar("client")


def get_client() -> "Client":
    client = _CLIENT.get(None)
    if not client:
        client = Client()
        set_client(client)
    return client


def set_client(client: "Client") -> contextvars.Token:
    return _CLIENT.set(client)


class Client:
    def __init__(self, http_client: httpx.AsyncClient = None) -> None:
        self._client = http_client

    async def post(self, route: str, **kwargs) -> httpx.Response:
        return await self._client.post(route, **kwargs)

    async def get(self, route: str) -> httpx.Response:
        return await self._client.get(route)


async def create_flow(flow: "Flow", client: Client = None) -> str:
    client = client or get_client()

    flow_data = api.schemas.Flow(
        name=flow.name,
        tags=flow.tags,
        parameters=flow.parameters,
    )
    response = await client.post("/flows/", json=flow_data.dict())

    flow_id = response.json().get("id")
    if not flow_id:
        raise Exception(f"Malformed response: {response}")

    # Return the id of the created flow
    return flow_id


async def read_flow(flow_id: str, client: Client = None) -> api.schemas.Flow:
    client = client or get_client()
    response = await client.get(f"/flows/{flow_id}")
    return api.schemas.Flow(**response.json())


async def create_flow_run(
    flow: "Flow",
    parameters: Dict[str, Any] = None,
    context: dict = None,
    extra_tags: Iterable[str] = None,
    parent_task_run_id: str = None,
    client: Client = None,
) -> str:
    client = client or get_client()
    tags = set(flow.tags).union(extra_tags or [])
    parameters = parameters or {}
    context = context or {}

    # Retrieve the flow id
    flow_id = await create_flow(flow, client=client)

    flow_run_data = api.schemas.FlowRun(
        flow_id=flow_id,
        flow_version=flow.version,
        parameters=parameters,
        context=context,
        tags=list(tags),
        parent_task_run_id=parent_task_run_id,
    )

    response = await client.post("/flow_runs/", json=flow_run_data.json_dict())
    flow_run_id = response.json().get("id")
    if not flow_run_id:
        raise Exception(f"Malformed response: {response}")

    return flow_run_id


async def read_flow_run(flow_run_id: str, client: Client = None) -> api.schemas.FlowRun:
    client = client or get_client()
    response = await client.get(f"/flow_runs/{flow_run_id}")
    return api.schemas.FlowRun(**response.json())


read_flow_sync = sync(read_flow)
create_flow_sync = sync(create_flow)
read_flow_run_sync = sync(read_flow_run)
create_flow_run_sync = sync(create_flow_run)
