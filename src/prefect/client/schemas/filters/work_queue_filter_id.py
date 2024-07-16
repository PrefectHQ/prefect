from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class WorkQueueFilterId(PrefectBaseModel):
    """Filter by `WorkQueue.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None,
        description="A list of work queue ids to include",
    )
