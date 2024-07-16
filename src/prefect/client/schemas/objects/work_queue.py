from typing import (
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect.types import (
    Name,
    NonNegativeInteger,
    PositiveInteger,
)

from .queue_filter import QueueFilter
from .work_queue_status import WorkQueueStatus


class WorkQueue(ObjectBaseModel):
    """An ORM representation of a work queue"""

    name: Name = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(
        default="", description="An optional description for the work queue."
    )
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[NonNegativeInteger] = Field(
        default=None, description="An optional concurrency limit for the work queue."
    )
    priority: PositiveInteger = Field(
        default=1,
        description=(
            "The queue's priority. Lower values are higher priority (1 is the highest)."
        ),
    )
    work_pool_name: Optional[str] = Field(default=None)
    # Will be required after a future migration
    work_pool_id: Optional[UUID] = Field(
        description="The work pool with which the queue is associated."
    )
    filter: Optional[QueueFilter] = Field(
        default=None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )
    last_polled: Optional[DateTime] = Field(
        default=None, description="The last time an agent polled this queue for work."
    )
    status: Optional[WorkQueueStatus] = Field(
        default=None, description="The queue status."
    )