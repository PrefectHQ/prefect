from __future__ import annotations

from typing import ClassVar

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerLogsSettings(PrefectBaseSettings):
    """
    Settings for controlling behavior of the logs subsystem
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "logs")
    )

    stream_out_enabled: bool = Field(
        default=False,
        description="Whether or not to stream logs out to the API via websockets.",
    )

    stream_publishing_enabled: bool = Field(
        default=False,
        description="Whether or not to publish logs to the streaming system.",
    )
