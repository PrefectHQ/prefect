from typing import Optional

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunFilterExpectedStartTime(PrefectBaseModel):
    """Filter by `FlowRun.expected_start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs scheduled to start at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs scheduled to start at or after this time",
    )
