from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class TelemetrySettings(PrefectBaseSettings):
    """
    Settings for configuring Prefect telemetry
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("telemetry",))

    enable_resource_metrics: bool = Field(
        default=True,
        description="Whether to enable OS-level resource metric collection in flow run subprocesses.",
    )

    resource_metrics_interval_seconds: int = Field(
        default=10,
        ge=1,
        description="Interval in seconds between resource metric collections.",
    )
