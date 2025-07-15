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
