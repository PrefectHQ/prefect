from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import StateType


class TaskRunFilterStateType(PrefectBaseModel):
    """Filter by `TaskRun.state_type`."""

    any_: Optional[List[StateType]] = Field(
        default=None, description="A list of task run state types to include"
    )
