from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerConcurrencySettings(PrefectBaseSettings):
    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "concurrency")
    )

    lease_storage: str = Field(
        default="prefect.server.concurrency.lease_storage.memory",
        description="The module to use for storing concurrency limit leases.",
    )

    initial_deployment_lease_duration: float = Field(
        default=300.0,
        ge=30.0,  # Minimum 30 seconds
        le=3600.0,  # Maximum 1 hour
        description="Initial duration for deployment concurrency lease in seconds.",
    )

    maximum_concurrency_slot_wait_seconds: float = Field(
        default=30,
        ge=0,
        description="The maximum number of seconds to wait before retrying when a concurrency slot cannot be acquired.",
    )
