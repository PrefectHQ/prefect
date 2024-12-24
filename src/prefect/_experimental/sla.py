import abc
from typing import Optional, Union

from pydantic import Field
from typing_extensions import TypeAlias

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.utilities.collections import AutoEnum


class SlaSeverity(AutoEnum):
    """The severity of a SLA violation"""

    MINOR = "minor"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ServiceLevelAgreement(ActionBaseModel, abc.ABC):
    """An ORM representation of a Service Level Agreement."""

    name: str = Field(
        default=...,
        description="The name of the SLA. Names must be unique on a per-deployment basis.",
    )
    severity: SlaSeverity = Field(
        default=...,
        description="The severity of the SLA.",
    )
    enabled: Optional[bool] = Field(
        default=True,
        description="Whether the SLA is enabled.",
    )


class TimeToCompletionSla(ServiceLevelAgreement):
    """An SLA that triggers when a flow run takes longer than the specified duration."""

    duration: int = Field(
        default=...,
        description="The maximum flow run duration allowed before the SLA is violated, expressed in seconds.",
    )


# Concrete SLA types
SlaTypes: TypeAlias = Union[TimeToCompletionSla]
