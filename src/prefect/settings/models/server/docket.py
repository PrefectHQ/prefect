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
        description=(
            "The URL of the Redis server to use for Docket. Supports the "
            "memory:// (single-server only), redis://, rediss://, "
            "redis+sentinel:// and rediss+sentinel:// schemes; the Sentinel "
            "schemes discover the current master through the listed Sentinel "
            "daemons and follow failover automatically (requires "
            "pydocket>=0.22.0)."
        ),
    )
