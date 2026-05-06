from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerDocketSettings(PrefectBaseSettings):
    """
    Settings for controlling Docket behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "docket")
    )

    name: str = Field(
        default="prefect-server",
        description="The name of the Docket instance.",
    )

    url: str = Field(
        default="memory://",
        description="The URL of the Redis server to use for Docket.",
    )

    worker_reconnect_base_delay_seconds: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Initial backoff (seconds) before restarting the docket worker "
            "after an unexpected failure. Delay doubles on each consecutive "
            "failure, capped by worker_reconnect_max_delay_seconds."
        ),
    )

    worker_reconnect_max_delay_seconds: float = Field(
        default=30.0,
        gt=0,
        description=(
            "Maximum backoff (seconds) between docket worker restart attempts."
        ),
    )

    worker_max_restart_attempts: int = Field(
        default=0,
        ge=0,
        description=(
            "Maximum number of consecutive docket worker restart attempts "
            "before giving up and letting the exception propagate. Set to 0 "
            "for unlimited restarts (recommended when a process supervisor "
            "such as Kubernetes will restart the pod on eventual crash)."
        ),
    )
