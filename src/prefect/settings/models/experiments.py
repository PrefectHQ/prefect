from __future__ import annotations

from typing import ClassVar, Optional

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class PluginsSettings(PrefectBaseSettings):
    """
    Settings for configuring the experimental plugin system
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("experiments", "plugins")
    )

    enabled: bool = Field(
        default=False,
        description="Enable the experimental plugin system.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_experimental_plugins",
            "prefect_plugins_enabled",
        ),
    )

    allow: Optional[str] = Field(
        default=None,
        description="Comma-separated list of plugin names to allow. If set, only these plugins will be loaded.",
    )

    deny: Optional[str] = Field(
        default=None,
        description="Comma-separated list of plugin names to deny. These plugins will not be loaded.",
    )

    setup_timeout_seconds: float = Field(
        default=20.0,
        description="Maximum time in seconds for all plugins to complete their setup hooks.",
    )

    strict: bool = Field(
        default=False,
        description="If True, exit if a required plugin fails during setup.",
    )

    safe_mode: bool = Field(
        default=False,
        description="If True, load plugins but do not execute their hooks. Useful for testing.",
    )


class ExperimentsSettings(PrefectBaseSettings):
    """
    Settings for configuring experimental features
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("experiments",))

    warn: bool = Field(
        default=True,
        description="If `True`, warn on usage of experimental features.",
        validation_alias=AliasChoices(
            AliasPath("warn"), "prefect_experiments_warn", "prefect_experimental_warn"
        ),
    )

    plugins: PluginsSettings = Field(
        default_factory=PluginsSettings,
        description="Settings for the experimental plugin system",
    )
