from typing import ClassVar, Optional

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import LogLevel


class RunnerServerSettings(PrefectBaseSettings):
    """
    Settings for controlling runner server behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("runner", "server")
    )

    enable: bool = Field(
        default=False,
        description="Whether or not to enable the runner's webserver.",
    )

    host: str = Field(
        default="localhost",
        description="The host address the runner's webserver should bind to.",
    )

    port: int = Field(
        default=8080,
        description="The port the runner's webserver should bind to.",
    )

    log_level: LogLevel = Field(
        default="ERROR",
        description="The log level of the runner's webserver.",
    )

    missed_polls_tolerance: int = Field(
        default=2,
        description="Number of missed polls before a runner is considered unhealthy by its webserver.",
    )


class RunnerSettings(PrefectBaseSettings):
    """
    Settings for controlling runner behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("runner",))

    process_limit: int = Field(
        default=5,
        description="Maximum number of processes a runner will execute in parallel.",
    )

    poll_frequency: int = Field(
        default=10,
        description="Number of seconds a runner should wait between queries for scheduled work.",
    )

    heartbeat_frequency: Optional[int] = Field(
        default=None,
        description="Number of seconds a runner should wait between heartbeats for flow runs.",
        ge=30,
    )

    crash_on_cancellation_failure: bool = Field(
        default=False,
        description=(
            "Whether to crash flow runs and shut down the runner when cancellation "
            "observing fails. When enabled, if both websocket and polling mechanisms "
            "for detecting cancellation events fail, all in-flight flow runs will be "
            "marked as crashed and the runner will shut down. When disabled (default), "
            "the runner will log an error but continue executing flow runs."
        ),
    )

    server: RunnerServerSettings = Field(
        default_factory=RunnerServerSettings,
        description="Settings for controlling runner server behavior",
    )
