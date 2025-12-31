from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class WorkerWebserverSettings(PrefectBaseSettings):
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("worker", "webserver")
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
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("worker",))

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

    enable_cancellation: bool = Field(
        default=False,
        description=(
            "Enable worker-side flow run cancellation for pending flow runs. "
            "When enabled, the worker will terminate infrastructure for flow runs "
            "that are cancelled while still in PENDING state (before the runner starts)."
        ),
    )

    cancellation_poll_seconds: float = Field(
        default=120,
        description=(
            "Number of seconds between polls for cancelling flow runs. "
            "Used as a fallback when the WebSocket connection for real-time "
            "cancellation events is unavailable."
        ),
    )

    webserver: WorkerWebserverSettings = Field(
        default_factory=WorkerWebserverSettings,
        description="Settings for a worker's webserver",
    )
