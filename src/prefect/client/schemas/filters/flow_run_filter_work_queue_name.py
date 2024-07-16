from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin


class FlowRunFilterWorkQueueName(PrefectBaseModel, OperatorMixin):
    """Filter by `FlowRun.work_queue_name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["work_queue_1", "work_queue_2"]],
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without work queue names",
    )