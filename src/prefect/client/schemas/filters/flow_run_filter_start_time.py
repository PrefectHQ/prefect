from typing import Optional

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunFilterStartTime(PrefectBaseModel):
    """Filter by `FlowRun.start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs starting at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs starting at or after this time",
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only return flow runs without a start time"
    )