from pydantic import Field

from prefect._internal.schemas.bases import ObjectBaseModel


class GlobalConcurrencyLimitResponse(ObjectBaseModel):
    """
    A response object for global concurrency limits.
    """

    active: bool = Field(
        default=True, description="Whether the global concurrency limit is active."
    )
    name: str = Field(
        default=..., description="The name of the global concurrency limit."
    )
    limit: int = Field(default=..., description="The concurrency limit.")
    active_slots: int = Field(default=..., description="The number of active slots.")
    slot_decay_per_second: float = Field(
        default=2.0,
        description="The decay rate for active slots when used as a rate limit.",
    )
