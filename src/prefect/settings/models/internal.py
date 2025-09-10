from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import LogLevel


class InternalSettings(PrefectBaseSettings):
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("internal",))

    logging_level: LogLevel = Field(
        default="ERROR",
        description="The default logging level for Prefect's internal machinery loggers.",
        validation_alias=AliasChoices(
            AliasPath("logging_level"),
            "prefect_internal_logging_level",
            "prefect_logging_internal_level",
        ),
    )

    v1_v2_concurrency_adapter_enabled: bool = Field(
        default=False,
        description=(
            "Enable the V1→V2 concurrency adapter for server endpoints. "
            "Intended for internal rollout control; subject to removal."
        ),
    )
