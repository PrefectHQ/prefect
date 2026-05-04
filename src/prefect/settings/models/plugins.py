from __future__ import annotations

from functools import partial
from typing import Annotated, ClassVar, Union

from pydantic import AliasChoices, AliasPath, BeforeValidator, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import validate_set_T_from_delim_string


class PluginsSettings(PrefectBaseSettings):
    """
    Settings for configuring the plugin system.

    Each field also accepts the legacy `PREFECT_EXPERIMENTS_PLUGINS_*` env-var
    name. The system warns once at import time when any of those legacy names
    is present in the environment.
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(("plugins",))

    enabled: bool = Field(
        default=False,
        description="Enable the plugin system.",
        validation_alias=AliasChoices(
            AliasPath("enabled"),
            "prefect_plugins_enabled",
            "prefect_experiments_plugins_enabled",
        ),
    )

    allow: Annotated[
        Union[set[str], None],
        BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
    ] = Field(
        default=None,
        description=(
            "Comma-separated list of plugin names to allow. If set, only these "
            "plugins will be loaded."
        ),
        validation_alias=AliasChoices(
            AliasPath("allow"),
            "prefect_plugins_allow",
            "prefect_experiments_plugins_allow",
        ),
    )

    deny: Annotated[
        Union[set[str], None],
        BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
    ] = Field(
        default=None,
        description=(
            "Comma-separated list of plugin names to deny. These plugins will "
            "not be loaded."
        ),
        validation_alias=AliasChoices(
            AliasPath("deny"),
            "prefect_plugins_deny",
            "prefect_experiments_plugins_deny",
        ),
    )

    setup_timeout_seconds: float = Field(
        default=20.0,
        description=(
            "Maximum time in seconds for all plugins to complete their setup hooks."
        ),
        validation_alias=AliasChoices(
            AliasPath("setup_timeout_seconds"),
            "prefect_plugins_setup_timeout_seconds",
            "prefect_experiments_plugins_setup_timeout_seconds",
        ),
    )

    strict: bool = Field(
        default=False,
        description="If True, exit if a required plugin fails during setup.",
        validation_alias=AliasChoices(
            AliasPath("strict"),
            "prefect_plugins_strict",
            "prefect_experiments_plugins_strict",
        ),
    )

    safe_mode: bool = Field(
        default=False,
        description=(
            "If True, load plugins but do not execute their hooks. Useful for testing."
        ),
        validation_alias=AliasChoices(
            AliasPath("safe_mode"),
            "prefect_plugins_safe_mode",
            "prefect_experiments_plugins_safe_mode",
        ),
    )


def _warn_on_deprecated_env_prefix() -> None:
    """
    Warn once per process if any `PREFECT_EXPERIMENTS_PLUGINS_*` env vars are
    set. The values still resolve via `AliasChoices`; this just signals the
    rename. Python's `warnings` machinery dedups on (message, category,
    module, lineno) so repeated settings instantiations do not spam.
    """
    import os
    import warnings

    old_prefix = "PREFECT_EXPERIMENTS_PLUGINS_"
    new_prefix = "PREFECT_PLUGINS_"
    found = sorted(k for k in os.environ if k.startswith(old_prefix))
    if not found:
        return

    pairs = ", ".join(
        f"{name} -> {new_prefix}{name[len(old_prefix) :]}" for name in found
    )
    warnings.warn(
        f"The {old_prefix}* environment variables are deprecated; rename to "
        f"{new_prefix}* ({pairs}). The old names continue to work for now "
        f"but will stop being recognized in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )


_warn_on_deprecated_env_prefix()
