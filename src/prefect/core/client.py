import httpx

from typing import TYPE_CHECKING

from prefect.orion import api

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Client:
    def __init__(
        self, base_url: str = None, http_client: httpx.AsyncClient = None
    ) -> None:
        self.base_url = base_url
        self._client = http_client or httpx.AsyncClient(base_url=base_url)

    async def post(self, route: str, json: dict) -> httpx.Response:
        return await self._client.post(route, json=json)

    async def get(self, route: str) -> httpx.Response:
        return await self._client.get(route)

    async def create_flow(self, flow: "Flow") -> str:
        flow_data = api.schemas.Flow(
            name=flow.name,
            tags=flow.tags,
            parameters=flow.parameters,
        )
        response = await self.post("/flows/", json=flow_data.dict())

        flow_id = response.json().get("id")
        if not flow_id:
            raise Exception(f"Malformed response: {response}")

        # Return the id of the created flow
        return flow_id

    async def read_flow(self, flow_id: str) -> api.schemas.Flow:
        response = await self.get(f"/flows/{flow_id}")
        return api.schemas.Flow(**response.json())
