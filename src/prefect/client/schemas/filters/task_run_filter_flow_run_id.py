from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class TaskRunFilterFlowRunId(PrefectBaseModel):
    """Filter by `TaskRun.flow_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run ids to include"
    )

    is_null_: bool = Field(
        default=False,
        description="If true, only include task runs without a flow run id",
    )