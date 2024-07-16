from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.types import (
    Name,
    NonNegativeFloat,
    NonNegativeInteger,
)


class GlobalConcurrencyLimitCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a global concurrency limit."""

    name: Name = Field(description="The name of the global concurrency limit.")
    limit: NonNegativeInteger = Field(
        description=(
            "The maximum number of slots that can be occupied on this concurrency"
            " limit."
        )
    )
    active: Optional[bool] = Field(
        default=True,
        description="Whether or not the concurrency limit is in an active state.",
    )
    active_slots: Optional[NonNegativeInteger] = Field(
        default=0,
        description="Number of tasks currently using a concurrency slot.",
    )
    slot_decay_per_second: Optional[NonNegativeFloat] = Field(
        default=0.0,
        description=(
            "Controls the rate at which slots are released when the concurrency limit"
            " is used as a rate limit."
        ),
    )