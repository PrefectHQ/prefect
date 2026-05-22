from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerWorkerChannelSettings(PrefectBaseSettings):
    """
    Settings for server-side worker channel storage and delivery policy.
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "worker_channel")
    )

    cleanup_queue_storage: str = Field(
        default="prefect.server.worker_communication.cleanup_queue.memory",
        description=(
            "The module to use for storing worker cleanup delivery messages. "
            "The default in-memory backend stores messages, leases, wakeups, "
            "and dead-letter entries only in the current server process; use a "
            "Redis-backed storage module for high availability or restart-safe "
            "cleanup delivery."
        ),
    )

    cleanup_lease_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="The default cleanup message reservation lease duration in seconds.",
    )

    cleanup_max_delivery_attempts: int = Field(
        default=3,
        ge=1,
        description=(
            "The maximum number of committed cleanup reservations before a "
            "message is moved to the dead-letter queue."
        ),
    )
