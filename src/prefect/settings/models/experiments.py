from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, ClassVar

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config

if TYPE_CHECKING:
    from prefect.settings.models.plugins import PluginsSettings


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

    @property
    def plugins(self) -> "PluginsSettings":
        """
        Deprecated. Access the plugin system settings via `settings.plugins`.

        Backed by the same env vars; the legacy `PREFECT_EXPERIMENTS_PLUGINS_*`
        names continue to resolve via `AliasChoices` on `PluginsSettings`.
        """
        warnings.warn(
            "`settings.experiments.plugins` is deprecated; use `settings.plugins` "
            "instead. The plugin system has graduated to GA.",
            DeprecationWarning,
            stacklevel=2,
        )
        from prefect.settings.context import get_current_settings

        return get_current_settings().plugins
