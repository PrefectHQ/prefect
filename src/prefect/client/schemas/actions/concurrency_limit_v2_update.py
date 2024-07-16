from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.types import (
    Name,
    NonNegativeFloat,
    NonNegativeInteger,
)


class ConcurrencyLimitV2Update(ActionBaseModel):
    """Data used by the Prefect REST API to update a v2 concurrency limit."""

    active: Optional[bool] = Field(None)
    name: Optional[Name] = Field(None)
    limit: Optional[NonNegativeInteger] = Field(None)
    active_slots: Optional[NonNegativeInteger] = Field(None)
    denied_slots: Optional[NonNegativeInteger] = Field(None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(None)
