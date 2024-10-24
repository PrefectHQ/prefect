from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class WorkerWebserverSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_WORKER_WEBSERVER_", env_file=".env", extra="ignore"
    )

    host: str = Field(
        default="0.0.0.0",
        description="The host address the worker's webserver should bind to.",
    )

    port: int = Field(
        default=8080,
        description="The port the worker's webserver should bind to.",
    )


class WorkerSettings(PrefectBaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PREFECT_WORKER_", env_file=".env", extra="ignore"
    )

    heartbeat_seconds: float = Field(
        default=30,
        description="Number of seconds a worker should wait between sending a heartbeat.",
    )

    query_seconds: float = Field(
        default=10,
        description="Number of seconds a worker should wait between queries for scheduled work.",
    )

    prefetch_seconds: float = Field(
        default=10,
        description="The number of seconds into the future a worker should query for scheduled work.",
    )

    webserver: WorkerWebserverSettings = Field(
        default_factory=WorkerWebserverSettings,
        description="Settings for a worker's webserver",
    )
