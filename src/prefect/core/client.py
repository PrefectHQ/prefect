from typing import TYPE_CHECKING

from prefect.orion import api

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Client:
    def __init__(self) -> None:
        pass

    async def create_flow(self, flow: "Flow") -> str:
        payload = api.schemas.Flow(
            name=flow.name,
            tags=flow.tags,
            parameters=flow.parameters,
        )
        response = await api.flows.create_flow(payload)
        if not response:
            # TODO: Create prefect exception types
            raise Exception("Failed to create flow")

        # Return the id of the created flow
        return response.id

    async def read_flow(self, flow_id: str) -> api.schemas.Flow:
        response = await api.flows.read_flow(flow_id)
        if not response:
            # TODO: Create prefect exception types
            raise Exception("Failed to read flow")

        # Return the found flow schema
        return response
