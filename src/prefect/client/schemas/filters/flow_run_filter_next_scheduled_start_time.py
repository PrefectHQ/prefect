from typing import Optional

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel


class FlowRunFilterNextScheduledStartTime(PrefectBaseModel):
    """Filter by `FlowRun.next_scheduled_start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include flow runs with a next_scheduled_start_time or before this"
            " time"
        ),
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include flow runs with a next_scheduled_start_time at or after this"
            " time"
        ),
    )