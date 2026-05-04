from __future__ import annotations

import warnings
from typing import ClassVar

from pydantic import AliasChoices, AliasPath, Field, PrivateAttr
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config
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

    # Bound by the root `Settings` model_validator so that
    # `settings.experiments.plugins` resolves on the same root instance
    # the user is holding — not on `get_current_settings()` (which can
    # diverge for tests/tooling that instantiate `Settings()` directly).
    _plugins_root: PluginsSettings | None = PrivateAttr(default=None)

    @property
    def plugins(self) -> PluginsSettings:
        """
        Deprecated. Use `settings.plugins` instead.

        Returns the same `PluginsSettings` instance that lives on the root
        `Settings` this `ExperimentsSettings` was attached to, so programmatic
        overrides on the parent are visible here. Falls back to a freshly
        built `PluginsSettings` (which still resolves env vars including the
        legacy `PREFECT_EXPERIMENTS_PLUGINS_*` names via `AliasChoices`) when
        this instance was constructed standalone.
        """
        warnings.warn(
            "`settings.experiments.plugins` is deprecated; use `settings.plugins` "
            "instead. The plugin system has graduated to GA.",
            DeprecationWarning,
            stacklevel=2,
        )
        if self._plugins_root is not None:
            return self._plugins_root
        return PluginsSettings()
