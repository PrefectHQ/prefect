from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class Sla(ActionBaseModel):
    """An ORM representation of a Service Level Agreement."""

    name: str = Field(
        default=...,
        description="The name of the SLA. Names must be unique on a per-deployment basis.",
    )
    enabled: Optional[bool] = Field(
        default=True,
        description="Whether the SLA is enabled.",
    )


class TimeToCompletionSla(Sla):
    """An SLA that triggers when a flow run takes longer than the specified duration."""

    duration: int = Field(
        default=...,
        description="The maximum flow run duration allowed before the SLA is violated, expressed in seconds.",
    )
