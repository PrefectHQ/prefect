from typing import ClassVar, Optional, Union

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class FlowsSettings(PrefectBaseSettings):
    """
    Settings for controlling flow behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("flows",))

    heartbeat_frequency: Optional[int] = Field(
        default=None,
        description="Number of seconds between flow run heartbeats. "
        "Heartbeats are used to detect crashed flow runs.",
        ge=30,
        validation_alias=AliasChoices(
            AliasPath("heartbeat_frequency"),
            "prefect_flows_heartbeat_frequency",
            # Legacy alias for backwards compatibility
            "prefect_runner_heartbeat_frequency",
        ),
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
