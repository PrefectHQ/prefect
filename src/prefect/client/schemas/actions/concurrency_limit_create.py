from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class ConcurrencyLimitCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a concurrency limit."""

    tag: str = Field(
        default=..., description="A tag the concurrency limit is applied to."
    )
    concurrency_limit: int = Field(default=..., description="The concurrency limit.")
