from typing import TYPE_CHECKING

from prefect.orion import api

if TYPE_CHECKING:
    from prefect.core.flow import Flow


class Client:
    def __init__(self) -> None:
        pass

    def create_flow(flow: "Flow") -> str:
        payload = api.schemas.Flow(
            name=flow.name,
            tags=flow.tags,
            parameters=flow.parameters,
        )
        response = api.flows.create_flow(payload)
        if not response:
            # TODO: Create prefect exception types
            raise Exception("Failed to create flow")

        # Return the id of the created flow
        return response.id
