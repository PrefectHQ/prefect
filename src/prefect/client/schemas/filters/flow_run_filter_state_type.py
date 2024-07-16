from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import StateType


class FlowRunFilterStateType(PrefectBaseModel):
    """Filter by `FlowRun.state_type`."""

    any_: Optional[List[StateType]] = Field(
        default=None, description="A list of flow run state types to include"
    )
    not_any_: Optional[List[StateType]] = Field(
        default=None, description="A list of flow run state types to exclude"
    )