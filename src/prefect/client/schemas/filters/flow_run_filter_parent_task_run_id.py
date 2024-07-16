from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin


class FlowRunFilterParentTaskRunId(PrefectBaseModel, OperatorMixin):
    """Filter by `FlowRun.parent_task_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run parent_task_run_ids to include"
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without parent_task_run_id",
    )