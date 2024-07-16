from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class ArtifactFilterFlowRunId(PrefectBaseModel):
    """Filter by `Artifact.flow_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run IDs to include"
    )
