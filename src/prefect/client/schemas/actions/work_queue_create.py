from typing import Optional

from pydantic import Field

from prefect.client.schemas.objects import QueueFilter
from prefect._internal.schemas.bases import ActionBaseModel


class WorkQueueCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a work queue."""

    name: str = Field(default=..., description="The name of the work queue.")
    description: Optional[str] = Field(None)
    is_paused: bool = Field(
        default=False,
        description="Whether the work queue is paused.",
    )
    concurrency_limit: Optional[int] = Field(
        default=None,
        description="A concurrency limit for the work queue.",
    )
    priority: Optional[int] = Field(
        default=None,
        description=(
            "The queue's priority. Lower values are higher priority (1 is the highest)."
        ),
    )

    # DEPRECATED

    filter: Optional[QueueFilter] = Field(
        None,
        description="DEPRECATED: Filter criteria for the work queue.",
        deprecated=True,
    )
