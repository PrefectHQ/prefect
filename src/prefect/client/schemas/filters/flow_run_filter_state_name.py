from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunFilterStateName(PrefectBaseModel):
    any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run state names to include"
    )
    not_any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run state names to exclude"
    )
