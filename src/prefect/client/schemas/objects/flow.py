from typing import (
    List,
)

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect.types import (
    Name,
)


class Flow(ObjectBaseModel):
    """An ORM representation of flow data."""

    name: Name = Field(
        default=..., description="The name of the flow", examples=["my-flow"]
    )
    tags: List[str] = Field(
        default_factory=list,
        description="A list of flow tags",
        examples=[["tag-1", "tag-2"]],
    )