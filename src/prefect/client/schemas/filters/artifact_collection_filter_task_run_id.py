from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class ArtifactCollectionFilterTaskRunId(PrefectBaseModel):
    """Filter by `ArtifactCollection.task_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of task run IDs to include"
    )
