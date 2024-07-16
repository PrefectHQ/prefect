from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.types import (
    Name,
    NonNegativeFloat,
    NonNegativeInteger,
)


class ConcurrencyLimitV2Create(ActionBaseModel):
    """Data used by the Prefect REST API to create a v2 concurrency limit."""

    active: bool = Field(
        default=True, description="Whether the concurrency limit is active."
    )
    name: Name = Field(default=..., description="The name of the concurrency limit.")
    limit: NonNegativeInteger = Field(default=..., description="The concurrency limit.")
    active_slots: NonNegativeInteger = Field(
        default=0, description="The number of active slots."
    )
    denied_slots: NonNegativeInteger = Field(
        default=0, description="The number of denied slots."
    )
    slot_decay_per_second: NonNegativeFloat = Field(
        default=0,
        description="The decay rate for active slots when used as a rate limit.",
    )