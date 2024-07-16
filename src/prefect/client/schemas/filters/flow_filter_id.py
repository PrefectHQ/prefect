from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowFilterId(PrefectBaseModel):
    """Filter by `Flow.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow ids to include"
    )