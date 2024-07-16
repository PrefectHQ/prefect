from typing import (
    Any,
    Optional,
)

from pydantic import (
    Field,
    model_validator,
)

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.validators import (
    set_run_policy_deprecated_fields,
)


class FlowRunPolicy(PrefectBaseModel):
    """Defines of how a flow run should be orchestrated."""

    max_retries: int = Field(
        default=0,
        description=(
            "The maximum number of retries. Field is not used. Please use `retries`"
            " instead."
        ),
        deprecated=True,
    )
    retry_delay_seconds: float = Field(
        default=0,
        description=(
            "The delay between retries. Field is not used. Please use `retry_delay`"
            " instead."
        ),
        deprecated=True,
    )
    retries: Optional[int] = Field(default=None, description="The number of retries.")
    retry_delay: Optional[int] = Field(
        default=None, description="The delay time between retries, in seconds."
    )
    pause_keys: Optional[set] = Field(
        default_factory=set, description="Tracks pauses this run has observed."
    )
    resuming: Optional[bool] = Field(
        default=False, description="Indicates if this run is resuming from a pause."
    )

    @model_validator(mode="before")
    @classmethod
    def populate_deprecated_fields(cls, values: Any):
        if isinstance(values, dict):
            return set_run_policy_deprecated_fields(values)
        return values