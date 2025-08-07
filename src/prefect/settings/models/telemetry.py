from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class TelemetrySettings(PrefectBaseSettings):
    """
    Settings for anonymous SDK usage telemetry.

    SDK telemetry helps us understand how Prefect is used and improve the product.
    No personal or sensitive data is collected. This is separate from server
    telemetry and OpenTelemetry tracing.
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("telemetry",))

    enabled: bool = Field(
        default=False,
        description=(
            "Enable anonymous SDK usage telemetry. "
            "No personal or sensitive data is collected."
        ),
    )

    endpoint: str = Field(
        default="https://sens-o-matic.prefect.io/sdk",
        description="Telemetry collection endpoint",
    )

    batch_size: int = Field(
        default=100,
        description="Number of events to batch before sending",
    )

    batch_interval_seconds: float = Field(
        default=300.0,  # 5 minutes
        description="Maximum time between telemetry sends",
    )
