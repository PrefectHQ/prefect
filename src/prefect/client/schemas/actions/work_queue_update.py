from typing import Optional

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from prefect.client.schemas.objects import QueueFilter
from prefect._internal.schemas.bases import ActionBaseModel


class WorkQueueUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a work queue."""

    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    is_paused: bool = Field(
        default=False, description="Whether or not the work queue is paused."
    )
    concurrency_limit: Optional[int] = Field(None)
    priority: Optional[int] = Field(None)
    last_polled: Optional[DateTime] = Field(None)

    # DEPRECATED

    filter: Optional[QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )
