from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.types import (
    Name,
    NonNegativeFloat,
    NonNegativeInteger,
)


class GlobalConcurrencyLimitUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a global concurrency limit."""

    name: Optional[Name] = Field(None)
    limit: Optional[NonNegativeInteger] = Field(None)
    active: Optional[bool] = Field(None)
    active_slots: Optional[NonNegativeInteger] = Field(None)
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(None)
