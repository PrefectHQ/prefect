import warnings
from typing import (
    List,
    Optional,
    Union,
)

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.validators import (
    list_length_50_or_less,
    validate_not_negative,
)


class TaskRunPolicy(PrefectBaseModel):
    """Defines of how a task run should retry."""

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
    retry_delay: Union[None, int, List[int]] = Field(
        default=None,
        description="A delay time or list of delay times between retries, in seconds.",
    )
    retry_jitter_factor: Optional[float] = Field(
        default=None, description="Determines the amount a retry should jitter"
    )

    @model_validator(mode="after")
    def populate_deprecated_fields(self):
        """
        If deprecated fields are provided, populate the corresponding new fields
        to preserve orchestration behavior.
        """
        # We have marked these fields as deprecated, so we need to filter out the
        # deprecation warnings _we're_ generating here
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            if not self.retries and self.max_retries != 0:
                self.retries = self.max_retries

            if not self.retry_delay and self.retry_delay_seconds != 0:
                self.retry_delay = self.retry_delay_seconds

        return self

    @field_validator("retry_delay")
    @classmethod
    def validate_configured_retry_delays(cls, v):
        return list_length_50_or_less(v)

    @field_validator("retry_jitter_factor")
    @classmethod
    def validate_jitter_factor(cls, v):
        return validate_not_negative(v)
