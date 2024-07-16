from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class TaskRunFilterStateName(PrefectBaseModel):
    any_: Optional[List[str]] = Field(
        default=None, description="A list of task run state names to include"
    )
