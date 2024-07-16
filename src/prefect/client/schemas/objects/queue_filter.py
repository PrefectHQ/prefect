from typing import (
    List,
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import PrefectBaseModel


class QueueFilter(PrefectBaseModel):
    """Filter criteria definition for a work queue."""

    tags: Optional[List[str]] = Field(
        default=None,
        description="Only include flow runs with these tags in the work queue.",
    )
    deployment_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Only include flow runs from these deployments in the work queue.",
    )