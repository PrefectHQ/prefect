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

    url: str = Field(
        default="redis://localhost:6379/0",  # TODO: Change to memory:// when we have a working version of `fakeredis`
        description="The URL of the Redis server to use for Docket.",
    )
