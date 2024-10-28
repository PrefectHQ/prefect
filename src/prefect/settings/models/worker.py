from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, PrefectSettingsConfigDict


class WorkerWebserverSettings(PrefectBaseSettings):
    model_config = PrefectSettingsConfigDict(
        env_prefix="PREFECT_WORKER_WEBSERVER_",
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=(
            "worker",
            "webserver",
        ),
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
    model_config = PrefectSettingsConfigDict(
        env_prefix="PREFECT_WORKER_",
        env_file=".env",
        extra="ignore",
        toml_file="prefect.toml",
        prefect_toml_table_header=("worker",),
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
