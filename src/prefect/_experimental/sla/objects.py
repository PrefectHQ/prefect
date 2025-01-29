from __future__ import annotations

import abc
from typing import Literal, Optional, Union
from uuid import UUID

from pydantic import Field, PrivateAttr, computed_field
from typing_extensions import Self, TypeAlias

from prefect._internal.schemas.bases import PrefectBaseModel


class ServiceLevelAgreement(PrefectBaseModel, abc.ABC):
    """An ORM representation of a Service Level Agreement."""

    _deployment_id: Optional[UUID] = PrivateAttr(default=None)

    name: str = Field(
        default=...,
        description="The name of the SLA. Names must be unique on a per-deployment basis.",
    )
    severity: Literal["minor", "low", "moderate", "high", "critical"] = Field(
        default="moderate",
        description="The severity of the SLA.",
    )
    enabled: Optional[bool] = Field(
        default=True,
        description="Whether the SLA is enabled.",
    )

    def set_deployment_id(self, deployment_id: UUID) -> Self:
        self._deployment_id = deployment_id
        return self

    @computed_field
    @property
    def owner_resource(self) -> Union[str, None]:
        if self._deployment_id:
            return f"prefect.deployment.{self._deployment_id}"
        return None


class TimeToCompletionSla(ServiceLevelAgreement):
    """An SLA that triggers when a flow run takes longer than the specified duration."""

    duration: int = Field(
        default=...,
        description="The maximum flow run duration allowed before the SLA is violated, expressed in seconds.",
    )


class SlaMergeResponse(PrefectBaseModel):
    """A response object for the apply_slas_for_deployment method. Contains the names of the created, updated, and deleted SLAs."""

    created: list[str]
    updated: list[str]
    deleted: list[str]


# Concrete SLA types
SlaTypes: TypeAlias = Union[TimeToCompletionSla]
