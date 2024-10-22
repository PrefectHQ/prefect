from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings
from prefect.types import LogLevel


class RunnerServerSettings(PrefectBaseSettings):
    """
    Settings for controlling runner server behavior
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_RUNNER_SERVER_", env_file=".env", extra="ignore"
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
        default="error",
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

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_RUNNER_", env_file=".env", extra="ignore"
    )

    process_limit: int = Field(
        default=5,
        description="Maximum number of processes a runner will execute in parallel.",
    )

    poll_frequency: int = Field(
        default=10,
        description="Number of seconds a runner should wait between queries for scheduled work.",
    )

    server: RunnerServerSettings = Field(
        default_factory=RunnerServerSettings,
        description="Settings for controlling runner server behavior",
    )
