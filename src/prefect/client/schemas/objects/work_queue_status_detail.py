from typing import (
    Optional,
)

from pydantic import (
    Field,
)
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel

from .work_queue_health_policy import WorkQueueHealthPolicy


class WorkQueueStatusDetail(PrefectBaseModel):
    healthy: bool = Field(..., description="Whether or not the work queue is healthy.")
    late_runs_count: int = Field(
        default=0, description="The number of late flow runs in the work queue."
    )
    last_polled: Optional[DateTime] = Field(
        default=None, description="The last time an agent polled this queue for work."
    )
    health_check_policy: WorkQueueHealthPolicy = Field(
        ...,
        description=(
            "The policy used to determine whether or not the work queue is healthy."
        ),
    )