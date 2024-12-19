from datetime import timedelta
from typing import Optional
from uuid import UUID

from pydantic import Field

from prefect.client.schemas.actions import ActionBaseModel


class Sla(ActionBaseModel):
    """An ORM representation of a Service Level Agreement."""

    name: str = Field(
        default=...,
        description="The name of the SLA. Names must be unique on a per-deployment basis.",
    )
    notification_block_id: Optional[UUID] = Field(
        default=None,
        description="The ID of the block document to use for notifications when the SLA is violated.",
    )
    enabled: Optional[bool] = Field(
        default=True,
        description="Whether the SLA is enabled.",
    )


class TimeToCompletionSla(Sla):
    """An SLA that triggers when a flow run takes longer than the specified duration."""

    duration: timedelta = Field(
        default=...,
        description="The maximum flow run duration allowed before the SLA is violated.",
    )
