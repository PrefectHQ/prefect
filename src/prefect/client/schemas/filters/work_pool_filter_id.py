from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class WorkPoolFilterId(PrefectBaseModel):
    """Filter by `WorkPool.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of work pool ids to include"
    )