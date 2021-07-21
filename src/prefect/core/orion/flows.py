from typing import TYPE_CHECKING
from prefect.core.utilities import sync

from prefect.orion import api
from prefect.core.orion.client import get_client

if TYPE_CHECKING:
    from prefect.core.flow import Flow
    from prefect.core.orion.client import Client


async def create_flow(flow: "Flow", client: "Client" = None) -> str:
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


async def read_flow(flow_id: str, client: "Client" = None) -> api.schemas.Flow:
    client = client or get_client()
    response = await client.get(f"/flows/{flow_id}")
    return api.schemas.Flow(**response.json())


read_flow_sync = sync(read_flow)
create_flow_sync = sync(create_flow)
