from typing import List

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class FlowCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a flow."""

    name: str = Field(
        default=..., description="The name of the flow", examples=["my-flow"]
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )
