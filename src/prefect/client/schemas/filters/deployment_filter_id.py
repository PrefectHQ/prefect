from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class DeploymentFilterId(PrefectBaseModel):
    """Filter by `Deployment.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of deployment ids to include"
    )