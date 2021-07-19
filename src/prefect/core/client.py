import httpx

from typing import TYPE_CHECKING, Iterable, Dict, Any

from prefect.orion import api

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Client:
    def __init__(
        self, base_url: str = None, http_client: httpx.AsyncClient = None
    ) -> None:
        self.base_url = base_url
        self._client = http_client or httpx.AsyncClient(base_url=base_url)

    async def post(self, route: str, **kwargs) -> httpx.Response:
        return await self._client.post(route, **kwargs)

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

        flow_run_data = api.schemas.FlowRun(
            flow_id=flow_id,
            flow_version=flow.version,
            parameters=parameters,
            context=context,
            tags=list(tags),
            parent_task_run_id=parent_task_run_id,
        )

        response = await self.post("/flow_runs/", data=flow_run_data.json())
        flow_run_id = response.json().get("id")
        if not flow_run_id:
            raise Exception(f"Malformed response: {response}")

        return flow_run_id

    async def read_flow_run(self, flow_run_id: str) -> api.schemas.FlowRun:
        response = await self.get(f"/flow_runs/{flow_run_id}")
        return api.schemas.FlowRun(**response.json())
