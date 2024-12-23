from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.utilities.collections import AutoEnum


class SLASeverity(AutoEnum):
    """The severity of a SLA violation"""

    MINOR = "minor"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    def code(self) -> str:
        match self:
            case SLASeverity.CRITICAL:
                return "SEV-1"
            case SLASeverity.HIGH:
                return "SEV-2"
            case SLASeverity.MODERATE:
                return "SEV-3"
            case SLASeverity.LOW:
                return "SEV-4"
            case SLASeverity.MINOR:
                return "SEV-5"
            case _:
                raise ValueError(f"Invalid severity: {self}")


class Sla(ActionBaseModel):
    """An ORM representation of a Service Level Agreement."""

    name: str = Field(
        default=...,
        description="The name of the SLA. Names must be unique on a per-deployment basis.",
    )
    severity: SLASeverity = Field(
        default=...,
        description="The severity of the SLA.",
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
