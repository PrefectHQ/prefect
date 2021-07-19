from typing import TYPE_CHECKING

from prefect.orion import api

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Client:
    def __init__(self, host_url: str) -> None:
        self.host_url = host_url

    async def post(route: str, json: dict):
        pass

    async def get(route: str):
        pass


async def create_flow(client: Client, flow: "Flow") -> str:
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


async def read_flow(client: Client, flow_id: str) -> api.schemas.Flow:
    response = await client.get(f"/flows/{flow_id}")
    return api.schemas.Flow(**response.json())
