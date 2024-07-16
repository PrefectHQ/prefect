from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class TaskRunFilterId(PrefectBaseModel):
    """Filter by `TaskRun.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of task run ids to include"
    )