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
            "and dead-letter entries only in the current server process; use "
            "an external storage module for high availability or restart-safe "
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

    snapshot_reconciliation_seconds: float = Field(
        default=300.0,
        gt=0.0,
        description=(
            "Maximum number of seconds between work-pool snapshot pushes on an "
            "idle worker channel connection. When no invalidation event arrives "
            "within this window, the server re-reads the work pool and pushes a "
            "fresh snapshot so workers self-heal from missed invalidations."
        ),
    )

    cleanup_completed_idempotency_retention_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description=(
            "How long completed cleanup idempotency records are retained after "
            "acknowledgement. None keeps them for the lifetime of the current "
            "server process. The in-memory backend does not survive restart; use "
            "external storage for high availability or restart-safe cleanup "
            "idempotency."
        ),
    )
