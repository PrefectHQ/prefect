from typing import Union

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class FlowsSettings(PrefectBaseSettings):
    """
    Settings for controlling flow behavior
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_FLOWS_", env_file=".env", extra="ignore"
    )

    default_retries: int = Field(
        default=0,
        ge=0,
        description="This value sets the default number of retries for all flows.",
        validation_alias=AliasChoices(
            AliasPath("default_retries"),
            "prefect_flows_default_retries",
            "prefect_flow_default_retries",
        ),
    )

    default_retry_delay_seconds: Union[int, float, list[float]] = Field(
        default=0,
        description="This value sets the default retry delay seconds for all flows.",
        validation_alias=AliasChoices(
            AliasPath("default_retry_delay_seconds"),
            "prefect_flows_default_retry_delay_seconds",
            "prefect_flow_default_retry_delay_seconds",
        ),
    )
